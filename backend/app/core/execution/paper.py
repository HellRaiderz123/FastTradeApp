from datetime import datetime
from typing import Dict, Any

from app.core.execution.base import ExecutionAdapter, get_ticket
from app.core.market.ltp import get_ltp
from app.core.utils.time import now_ist


class PaperExecutionAdapter(ExecutionAdapter):
    """
    Simulates execution using live LTP.
    """

    @staticmethod
    def _resolve_leg_qty(leg: Dict[str, Any], ticket_qty: int) -> int:
        raw = leg.get("qty", leg.get("quantity"))
        if raw is None:
            return max(1, int(ticket_qty))
        try:
            value = int(raw)
        except Exception:
            return max(1, int(ticket_qty))
        if value <= 0:
            return max(1, int(ticket_qty))
        # If leg qty already equals ticket_qty, it's the total — don't multiply again.
        # Only multiply when leg qty looks like a lot count (< ticket_qty), which
        # happens for options where lot_size > 1 and qty stores lots not shares.
        if value < ticket_qty and ticket_qty > 1:
            return value * ticket_qty
        return value

    def estimate_margin_required(self, intent, entry_credit_total: float | None = None) -> float:
        """
        Fetch real margin from the active broker's margin API.
        Falls back to spread-width estimate if broker API is unavailable.
        """
        from app.core.broker.registry import get_active_broker
        broker = get_active_broker()

        # --- INDMoney: call basket margin API ---
        if broker == "indmoney":
            try:
                from app.core.broker.indmoney.client import get_indmoney_client
                client = get_indmoney_client()
                ticket = get_ticket(intent)
                qty = int(ticket.get("lot_size", 1)) * int(ticket.get("lots", 1))
                basket = []
                for leg in ticket.get("legs", []):
                    sym = leg.get("symbol", "")
                    import re as _re
                    m = _re.match(r'^[A-Z]+_([0-9]+)$', sym.strip().upper())
                    sec_id = m.group(1) if m else sym
                    leg_qty = qty * int(leg.get("lots_multiplier", 1) or 1)
                    basket.append({
                        "security_id": sec_id,
                        "exchange": "NSE",
                        "segment": "DERIVATIVE",
                        "txn_type": str(leg.get("side", "BUY")).upper(),
                        "qty": leg_qty,
                        "order_type": "MARKET",
                        "product": "MARGIN",
                    })
                resp = client.get_margin_basket(basket)
                margin_val = (
                    resp.get("total_margin")
                    or resp.get("margin_required")
                    or (resp.get("data") or {}).get("total_margin")
                    or (resp.get("data") or {}).get("margin_required")
                )
                if margin_val and float(margin_val) > 0:
                    return round(float(margin_val), 2)
            except Exception:
                pass

        # --- Zerodha: call basket margin API ---
        if broker == "zerodha":
            try:
                from app.core.broker.zerodha.client import get_kite_client
                from app.core.execution.zerodha import ZerodhaExecutionAdapter
                kite = get_kite_client()
                margin = ZerodhaExecutionAdapter(kite_client=kite, dry_run=True).calculate_margin_required(intent)
                if margin and float(margin) > 0:
                    return round(float(margin), 2)
            except Exception:
                pass

        # --- Fallback: spread-width estimate ---
        try:
            ticket = get_ticket(intent)
            qty = int(ticket.get("lot_size", 1)) * int(ticket.get("lots", 1))
            entry_value = abs(float(
                entry_credit_total
                if entry_credit_total is not None
                else getattr(intent, "entry_credit", 0.0) or 0.0
            ))
            short_count = 0
            side_widths: list[float] = []

            for opt_type in ("CE", "PE"):
                sells: list[float] = []
                buys: list[float] = []
                for leg in ticket.get("legs", []):
                    if str(leg.get("type", "")).upper() != opt_type:
                        continue
                    strike = float(leg.get("strike", 0) or 0)
                    if strike <= 0:
                        continue
                    side = str(leg.get("side", "")).upper()
                    if side == "SELL":
                        short_count += 1
                        sells.append(strike)
                    elif side == "BUY":
                        buys.append(strike)

                protected_risk = 0.0
                for sell_strike in sells:
                    hedges = [b for b in buys if b >= sell_strike] if opt_type == "CE" else [b for b in buys if b <= sell_strike]
                    if hedges:
                        width = min(abs(h - sell_strike) for h in hedges)
                        protected_risk += width * qty
                if protected_risk > 0:
                    side_widths.append(protected_risk)

            if side_widths:
                estimated = max(side_widths) if len(side_widths) >= 2 else sum(side_widths)
                return round(max(float(estimated), entry_value), 2)

            if short_count > 0:
                return round(max(entry_value * 8.0, entry_value), 2)

            return round(entry_value, 2)
        except Exception:
            return round(abs(float(entry_credit_total or 0.0)), 2)

    def execute(self, intent):
        ticket = get_ticket(intent)
        ticket_qty = int(ticket.get("lot_size", 1)) * int(ticket.get("lots", 1))

        # 1️⃣ Build symbol list (prefer stored symbol if exists)
        symbols = []
        for leg in ticket["legs"]:
            symbol = leg.get("symbol") or f'{leg["strike"]}{leg["type"]}'
            leg["symbol"] = symbol          # 🔐 normalize once
            symbols.append(symbol)

        # 2️⃣ Fetch LTP
        ltp_map = get_ltp(symbols)

        entry_credit = 0.0

        # 3️⃣ 🔥 STORE EXECUTED PRICE PER LEG (CRITICAL)
        # For INDMoney option symbols missing from instruments cache, retry once with a forced
        # cache refresh before falling back to 0 (avoids blocking paper execution entirely).
        from app.core.market.provider import is_indstocks
        _indstocks = is_indstocks()
        _missing_options = [
            leg["symbol"] for leg in ticket["legs"]
            if ltp_map.get(leg["symbol"]) is None
            and _indstocks
            and leg["symbol"].upper().endswith(("CE", "PE"))
        ]
        if _missing_options:
            # Force instruments cache refresh and retry LTP for missing option symbols
            try:
                from app.core.broker.indstocks.market_data import _refresh_instruments_cache
                _refresh_instruments_cache()
                retry_map = get_ltp(_missing_options)
                ltp_map.update(retry_map)
            except Exception:
                pass

        for leg in ticket["legs"]:
            symbol = leg["symbol"]
            price = ltp_map.get(symbol)
            if price is None or price == 0.0:
                if _indstocks and symbol.upper().endswith(("CE", "PE")):
                    import logging as _log
                    _log.getLogger(__name__).warning(
                        "LTP not found for option symbol '%s' in INDMoney instruments cache (source=fno). "
                        "Using 0 as fallback price. Ensure INDMONEY_ACCESS_TOKEN is valid.",
                        symbol,
                    )
                    price = 0.0
                else:
                    raise ValueError(f"LTP not found for symbol: {symbol}")

            leg["price"] = price            # ✅ THIS LINE FIXES EVERYTHING
            leg_qty = self._resolve_leg_qty(leg, ticket_qty)
            leg["qty"] = leg_qty

            if leg["side"] == "SELL":
                entry_credit += price * leg_qty
            else:
                entry_credit -= price * leg_qty

        entry_credit_total = round(entry_credit, 2)
        margin_required = self.estimate_margin_required(intent, entry_credit_total)

        # 4️⃣ Return execution snapshot
        return {
            "filled_at": now_ist().isoformat(),
            "entry_credit": entry_credit_total,
            "margin_required": margin_required,
            "ltp_used": ltp_map,
            "mode": "PAPER",
        }


    def mtm(self, intent) -> float:
        """
        Unrealized PnL for paper trades. Writes leg_pnl + ltp back into ticket legs.
        """
        ticket = get_ticket(intent)
        ticket_qty = int(ticket.get("lot_size", 1)) * int(ticket.get("lots", 1))

        symbols = [leg.get("symbol") or f'{leg["strike"]}{leg["type"]}' for leg in ticket["legs"]]
        ltp_map = get_ltp(symbols)

        pnl = 0.0
        for leg in ticket["legs"]:
            symbol = leg.get("symbol") or f'{leg["strike"]}{leg["type"]}'
            current = ltp_map.get(symbol)
            entry = leg.get("price") or leg.get("premium")
            if entry is None or current is None or float(current) <= 0:
                continue
            m = int(leg.get("lots_multiplier", 1) or 1)
            leg_qty = self._resolve_leg_qty(leg, ticket_qty) * m if leg.get("qty") is None else self._resolve_leg_qty(leg, ticket_qty)
            side = (leg.get("side") or leg.get("action") or "").upper()
            sign = 1.0 if side == "SELL" else -1.0
            leg_pnl = (float(entry) - float(current)) * sign * leg_qty
            leg["ltp"] = round(float(current), 2)
            leg["leg_pnl"] = round(leg_pnl, 2)
            pnl += leg_pnl

        # Persist updated leg data back into ticket
        intent.ticket = ticket
        return round(pnl, 2)

    def exit(self, intent):
        ticket = get_ticket(intent)
        ticket_qty = int(ticket.get("lot_size", 1)) * int(ticket.get("lots", 1))
        symbols = [leg["symbol"] for leg in ticket["legs"]]

        ltp_map = get_ltp(symbols)

        from app.core.market.provider import is_indstocks
        _indstocks = is_indstocks()
        _missing = [
            s for s in symbols
            if ltp_map.get(s) is None and _indstocks and s.upper().endswith(("CE", "PE"))
        ]
        if _missing:
            try:
                from app.core.broker.indstocks.market_data import _refresh_instruments_cache
                _refresh_instruments_cache()
                ltp_map.update(get_ltp(_missing))
            except Exception:
                pass

        import logging as _log
        _logger = _log.getLogger(__name__)

        exit_cost = 0.0
        for leg in ticket["legs"]:
            symbol = leg.get("symbol") or leg.get("tradingsymbol", "")
            price = ltp_map.get(symbol)
            if price is None or float(price) <= 0:
                if _indstocks and symbol.upper().endswith(("CE", "PE")):
                    _logger.warning(
                        "Exit LTP not found for option symbol '%s' — using entry price as fallback.",
                        symbol,
                    )
                    price = float(leg.get("price") or leg.get("premium") or 0.0)
                else:
                    raise ValueError(f"LTP not found for symbol: {symbol}")
            leg_qty = self._resolve_leg_qty(leg, ticket_qty)
            side = (leg.get("side") or leg.get("action") or "").upper()
            if side == "SELL":
                exit_cost += price * leg_qty
            else:
                exit_cost -= price * leg_qty

        # Calculate final P&L
        entry_credit_total = float(intent.entry_credit or 0.0)
        exit_cost_total = exit_cost
        final_pnl = round(entry_credit_total - exit_cost_total, 2)

        return {
            "mode": "PAPER",
            "exit_cost": exit_cost_total,
            "final_pnl": final_pnl,
            "closed_at": now_ist().isoformat(),
        }
    