from datetime import datetime
from typing import Dict, Any

from app.core.market.ltp import get_ltp


def execute_paper_trade(ticket: dict) -> Dict[str, Any]:
    """
    Simulate execution using live LTP.
    """
    symbols = []

    for leg in ticket["legs"]:
        symbols.append(f'{leg["strike"]}{leg["type"]}')

    ltp_map = get_ltp(symbols)

    total_credit = 0.0

    for leg in ticket["legs"]:
        sym = f'{leg["strike"]}{leg["type"]}'
        price = ltp_map.get(sym, 0.0)

        if leg["side"] == "SELL":
            total_credit += price
        else:
            total_credit -= price

    return {
        "filled_at": datetime.utcnow().isoformat(),
        "total_credit": total_credit,
        "ltp_used": ltp_map,
        "mode": "PAPER",
    }
