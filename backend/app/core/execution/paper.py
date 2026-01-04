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
        symbols = []

        for leg in ticket["legs"]:
            symbols.append(f'{leg["strike"]}{leg["type"]}')

        ltp = get_ltp(symbols)

        credit = 0.0

        for leg in ticket["legs"]:
            sym = f'{leg["strike"]}{leg["type"]}'
            price = ltp[sym]

            if leg["side"] == "SELL":
                credit += price
            else:
                credit -= price

        return {
            "filled_at": now_ist().isoformat(),
            "entry_credit": credit,
            "ltp_used": ltp,
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

    def exit(self, intent) -> Dict[str, Any]:
        """
        Close paper trade immediately at LTP.
        """
        pnl = self.mtm(intent)

        return {
            "exited_at": now_ist().isoformat(),
            "mode": "PAPER",
            "reason": "MANUAL_EXIT",
        }
    