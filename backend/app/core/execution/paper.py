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
            price = ltp_map[symbol]

            leg["price"] = price            # ✅ THIS LINE FIXES EVERYTHING

            if leg["side"] == "SELL":
                entry_credit += price
            else:
                entry_credit -= price

        # 4️⃣ Return execution snapshot
        return {
            "filled_at": now_ist().isoformat(),
            "entry_credit": entry_credit,
            "ltp_used": ltp_map,
            "mode": "PAPER",
        }


    def mtm(self, intent) -> float:
        """
        Unrealized PnL for paper trades.
        """
        ticket = intent.ticket
        symbols = [f'{l["strike"]}{l["type"]}' for l in ticket["legs"]]
        ltp_map = get_ltp(symbols)

        pnl = 0.0
        for leg in ticket["legs"]:
            sym = f'{leg["strike"]}{leg["type"]}'
            price = ltp_map.get(sym, 0.0)

            if leg["side"] == "SELL":
                pnl += price
            else:
                pnl -= price

        return pnl

    def exit(self, intent):
        ticket = intent.ticket
        symbols = [leg["symbol"] for leg in ticket["legs"]]

        ltp_map = get_ltp(symbols)

        exit_cost = 0.0
        for leg in ticket["legs"]:
            price = ltp_map[leg["symbol"]]
            if leg["side"] == "SELL":
                exit_cost += price
            else:
                exit_cost -= price

        final_pnl = round(intent.entry_credit - exit_cost, 2)

        return {
            "mode": "PAPER",
            "exit_cost": exit_cost,
            "final_pnl": final_pnl,
            "closed_at": now_ist().isoformat(),
        }
    