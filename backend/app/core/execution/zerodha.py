import os
from typing import Dict, Any, List

from app.core.market.ltp import get_ltp
from app.core.utils.time import now_ist
from app.core.broker.zerodha_symbols import build_zerodha_option_symbol


class ZerodhaExecutionAdapter:
    def __init__(self, kite_client, dry_run: bool = True):
        self.kite = kite_client
        self.dry_run = dry_run

    # ============================
    # EXECUTION (DRY-RUN ONLY)
    # ============================
    def execute(self, intent) -> Dict[str, Any]:
        orders = self._build_orders(intent)

        # Estimate entry credit using current LTP and store per-leg price for MTM
        entry_credit_total = self._estimate_entry_credit_and_store_leg_prices(intent)

        if self.dry_run:
            return {
                "mode": "ZERODHA_DRY_RUN",
                "orders": orders,
                "created_at": now_ist().isoformat(),
                "entry_credit": entry_credit_total,
            }

        product = os.getenv("ZERODHA_PRODUCT", "NRML")
        placed = []
        for o in orders:
            order_id = self.kite.place_order(
                variety=getattr(self.kite, "VARIETY_REGULAR", "regular"),
                exchange=o["exchange"],
                tradingsymbol=o["tradingsymbol"],
                transaction_type=o["transaction_type"],
                quantity=int(o["quantity"]),
                order_type=getattr(self.kite, "ORDER_TYPE_MARKET", "MARKET"),
                product=getattr(self.kite, "PRODUCT_NRML", product) if product == "NRML" else product,
                validity=getattr(self.kite, "VALIDITY_DAY", "DAY"),
            )
            placed.append({"order_id": order_id, "order": o})

        return {
            "mode": "ZERODHA_LIVE",
            "orders": orders,
            "placed": placed,
            "filled_at": now_ist().isoformat(),
            "entry_credit": entry_credit_total,
        }

    # ============================
    # EXIT
    # ============================
    def exit(self, intent) -> Dict[str, Any]:
        exit_orders = self._build_exit_orders(intent)

        # Estimate cost to close using LTP
        final_pnl, exit_cost_total = self._estimate_exit_cost_and_pnl(intent)

        if self.dry_run:
            return {
                "mode": "ZERODHA_DRY_RUN",
                "exit_orders": exit_orders,
                "exited_at": now_ist().isoformat(),
                "exit_cost": exit_cost_total,
                "final_pnl": final_pnl,
            }

        product = os.getenv("ZERODHA_PRODUCT", "NRML")
        placed = []
        for o in exit_orders:
            order_id = self.kite.place_order(
                variety=getattr(self.kite, "VARIETY_REGULAR", "regular"),
                exchange=o["exchange"],
                tradingsymbol=o["tradingsymbol"],
                transaction_type=o["transaction_type"],
                quantity=int(o["quantity"]),
                order_type=getattr(self.kite, "ORDER_TYPE_MARKET", "MARKET"),
                product=getattr(self.kite, "PRODUCT_NRML", product) if product == "NRML" else product,
                validity=getattr(self.kite, "VALIDITY_DAY", "DAY"),
            )
            placed.append({"order_id": order_id, "order": o})

        return {
            "mode": "ZERODHA_LIVE",
            "exit_orders": exit_orders,
            "placed": placed,
            "closed_at": now_ist().isoformat(),
            "exit_cost": exit_cost_total,
            "final_pnl": final_pnl,
        }

    # ============================
    # ORDER BUILDERS
    # ============================
    def _build_orders(self, intent) -> List[Dict[str, Any]]:
        ticket = intent.ticket
        qty = ticket["lots"] * ticket["lot_size"]

        orders = []

        for leg in ticket["legs"]:
            tradingsymbol = build_zerodha_option_symbol(
                underlying=intent.underlying,
                expiry=intent.expiry,          # ✅ REQUIRED
                strike=leg["strike"],
                option_type=leg["type"],
            )

            orders.append({
                "tradingsymbol": tradingsymbol,
                "exchange": "NFO",
                "transaction_type": "SELL" if leg["side"] == "SELL" else "BUY",
                "quantity": qty,
                "order_type": "MARKET",
                "product": "NRML",
                "validity": "DAY",
            })

        return orders

    def _build_exit_orders(self, intent) -> List[Dict[str, Any]]:
        ticket = intent.ticket
        qty = ticket["lots"] * ticket["lot_size"]

        exit_orders = []

        for leg in ticket["legs"]:
            tradingsymbol = build_zerodha_option_symbol(
                underlying=intent.underlying,
                expiry=intent.expiry,
                strike=leg["strike"],
                option_type=leg["type"],
            )

            exit_orders.append({
                "tradingsymbol": tradingsymbol,
                "exchange": "NFO",
                "transaction_type": "BUY" if leg["side"] == "SELL" else "SELL",
                "quantity": qty,
                "order_type": "MARKET",
                "product": "NRML",
                "validity": "DAY",
            })

        return exit_orders

    # ============================
    # MTM (READ ONLY)
    # ============================
    def mtm(self, intent) -> float:
        """
        Mark-to-market PnL using Zerodha LTP.
        Requires entry_price per leg.
        """

        ticket = intent.ticket
        qty = ticket["lot_size"] * ticket["lots"]

        symbols = [leg.get("symbol") for leg in ticket.get("legs", []) if leg.get("symbol")]
        ltp_map = get_ltp(symbols)

        pnl = 0.0

        for leg in ticket["legs"]:
            sym = leg.get("symbol")
            if not sym:
                continue
            ltp = float(ltp_map.get(sym) or 0.0)
            entry = leg.get("price")
            if entry is None:
                continue
            entry_f = float(entry)

            if leg["side"] == "SELL":
                pnl += (entry_f - ltp) * qty
            else:
                pnl += (ltp - entry_f) * qty

        return pnl

    def _estimate_entry_credit_and_store_leg_prices(self, intent) -> float:
        ticket = intent.ticket
        qty = int(ticket.get("lot_size", 1)) * int(ticket.get("lots", 1))

        # Ensure tradingsymbol exists on each leg (for MTM)
        symbols: List[str] = []
        for leg in ticket.get("legs", []):
            sym = leg.get("symbol")
            if not sym:
                # Build from strike/type if missing
                sym = build_zerodha_option_symbol(
                    underlying=intent.underlying,
                    expiry=intent.expiry,
                    strike=int(leg["strike"]),
                    option_type=str(leg["type"]),
                )
                leg["symbol"] = sym
            symbols.append(sym)

        ltp = get_ltp(symbols)

        entry_credit_per_unit = 0.0
        for leg in ticket.get("legs", []):
            sym = leg.get("symbol")
            px = float(ltp.get(sym) or 0.0)
            leg["price"] = px
            if leg.get("side") == "SELL":
                entry_credit_per_unit += px
            else:
                entry_credit_per_unit -= px

        return round(entry_credit_per_unit * qty, 2)

    def _estimate_exit_cost_and_pnl(self, intent) -> tuple[float, float]:
        ticket = intent.ticket
        qty = int(ticket.get("lot_size", 1)) * int(ticket.get("lots", 1))
        symbols = [leg.get("symbol") for leg in ticket.get("legs", []) if leg.get("symbol")]
        ltp = get_ltp(symbols)

        exit_cost_per_unit = 0.0
        for leg in ticket.get("legs", []):
            sym = leg.get("symbol")
            if not sym:
                continue
            px = float(ltp.get(sym) or 0.0)
            if leg.get("side") == "SELL":
                exit_cost_per_unit += px
            else:
                exit_cost_per_unit -= px

        exit_cost_total = float(exit_cost_per_unit) * float(qty)
        entry_credit_total = float(getattr(intent, "entry_credit", 0.0) or 0.0)
        final_pnl = round(entry_credit_total - exit_cost_total, 2)
        return float(final_pnl), round(exit_cost_total, 2)
