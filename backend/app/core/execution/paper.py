from datetime import datetime
from typing import Dict, Any

from app.core.execution.base import ExecutionAdapter, get_ticket
from app.core.market.ltp import get_ltp
from app.core.utils.time import now_ist
from app.core.broker.zerodha.client import get_kite_client
from app.core.execution.zerodha import ZerodhaExecutionAdapter


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
        if value <= 10 and ticket_qty > 1:
            return value * ticket_qty
        return value

    def estimate_margin_required(self, intent, entry_credit_total: float | None = None) -> float:
        """
        Estimate broker-style margin for paper trades so the UI can show a
        realistic capital block / return-on-margin similar to Zerodha.
        """
        try:
            kite = get_kite_client()
            margin = ZerodhaExecutionAdapter(kite_client=kite, dry_run=True).calculate_margin_required(intent)
            if margin and float(margin) > 0:
                return round(float(margin), 2)
        except Exception:
            pass

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
        for leg in ticket["legs"]:
            symbol = leg["symbol"]
            price = ltp_map.get(symbol)
            if price is None or price == 0.0:
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
        Unrealized PnL for paper trades.
        """
        ticket = get_ticket(intent)
        ticket_qty = int(ticket.get("lot_size", 1)) * int(ticket.get("lots", 1))

        symbols = [leg.get("symbol") or f'{leg["strike"]}{leg["type"]}' for leg in ticket["legs"]]
        ltp_map = get_ltp(symbols)

        pnl = 0.0
        for leg in ticket["legs"]:
            symbol = leg.get("symbol") or f'{leg["strike"]}{leg["type"]}'
            current = ltp_map.get(symbol, 0.0)
            entry = leg.get("price")
            if entry is None:
                raise ValueError("Leg price missing for MTM")
            leg_qty = self._resolve_leg_qty(leg, ticket_qty)
            sign = 1.0 if leg["side"] == "SELL" else -1.0
            pnl += (float(entry) - float(current)) * sign * leg_qty

        return round(pnl, 2)

    def exit(self, intent):
        ticket = get_ticket(intent)
        ticket_qty = int(ticket.get("lot_size", 1)) * int(ticket.get("lots", 1))
        symbols = [leg["symbol"] for leg in ticket["legs"]]

        ltp_map = get_ltp(symbols)

        exit_cost = 0.0
        for leg in ticket["legs"]:
            price = ltp_map.get(leg["symbol"])
            if price is None or price == 0.0:
                raise ValueError(f"LTP not found for symbol: {leg['symbol']}")
            leg_qty = self._resolve_leg_qty(leg, ticket_qty)
            if leg["side"] == "SELL":
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
    