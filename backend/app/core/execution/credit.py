from typing import Dict, Any
from app.core.market.ltp import get_ltp


def compute_entry_credit(ticket: Dict) -> float:
    """
    Computes net credit/debit at entry using LTP.
    """
    credit = 0.0

    for leg in ticket["legs"]:
        price = leg.get("price")
        if price is None:
            raise ValueError("Leg price missing for entry credit")

        if leg["side"] == "SELL":
            credit += price
        else:
            credit -= price

    return round(credit, 2)