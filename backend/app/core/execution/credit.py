from typing import Dict, Any
from app.core.market.ltp import get_ltp


def compute_entry_credit(ticket: Dict[str, Any]) -> float:
    symbols = [
        f'{leg["strike"]}{leg["type"]}'
        for leg in ticket["legs"]
    ]

    ltp = get_ltp(symbols)

    credit = 0.0
    for leg in ticket["legs"]:
        sym = f'{leg["strike"]}{leg["type"]}'
        price = ltp[sym]

        if leg["side"] == "SELL":
            credit += price
        else:
            credit -= price

    return credit
