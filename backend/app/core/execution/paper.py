from datetime import datetime
from typing import Dict, Any

from app.core.execution.base import ExecutionAdapter
from app.core.market.ltp import get_ltp
from app.core.utils.time import now_ist


class PaperExecutionAdapter(ExecutionAdapter):
    """
    Simulates execution using live LTP.
    """

    def execute(self, intent):
        ticket = intent.ticket

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
            leg_qty = int(leg.get("qty", 1))

            if leg["side"] == "SELL":
                entry_credit += price * leg_qty
            else:
                entry_credit -= price * leg_qty

        entry_credit_total = round(entry_credit, 2)

        # 4️⃣ Return execution snapshot
        return {
            "filled_at": now_ist().isoformat(),
            "entry_credit": entry_credit_total,
            "ltp_used": ltp_map,
            "mode": "PAPER",
        }


    def mtm(self, intent) -> float:
        """
        Unrealized PnL for paper trades.
        """
        ticket = intent.ticket

        symbols = [leg.get("symbol") or f'{leg["strike"]}{leg["type"]}' for leg in ticket["legs"]]
        ltp_map = get_ltp(symbols)

        pnl = 0.0
        for leg in ticket["legs"]:
            symbol = leg.get("symbol") or f'{leg["strike"]}{leg["type"]}'
            current = ltp_map.get(symbol, 0.0)
            entry = leg.get("price")
            if entry is None:
                raise ValueError("Leg price missing for MTM")
            leg_qty = int(leg.get("qty", 1))
            sign = 1.0 if leg["side"] == "SELL" else -1.0
            pnl += (float(entry) - float(current)) * sign * leg_qty

        return round(pnl, 2)

    def exit(self, intent):
        ticket = intent.ticket
        symbols = [leg["symbol"] for leg in ticket["legs"]]

        ltp_map = get_ltp(symbols)

        exit_cost = 0.0
        for leg in ticket["legs"]:
            price = ltp_map.get(leg["symbol"])
            if price is None or price == 0.0:
                raise ValueError(f"LTP not found for symbol: {leg['symbol']}")
            leg_qty = int(leg.get("qty", 1))
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
    