from typing import Dict, Any
from app.core.market.ltp import get_ltp


def compute_entry_credit(ticket: Dict) -> float:
    """
    Computes net credit/debit at entry using LTP.
    """
    credit = 0.0

    qty = int(ticket.get("lot_size", 1)) * int(ticket.get("lots", 1))

    for leg in ticket["legs"]:
        price = leg.get("price")
        if price is None:
            raise ValueError("Leg price missing for entry credit")

        if leg["side"] == "SELL":
            credit += price
        else:
            credit -= price

    return round(credit, 2)


def compute_entry_credit_total(ticket: Dict) -> float:
    """Total entry credit/debit in ₹ including lot quantity."""
    per_unit = compute_entry_credit(ticket)
    qty = int(ticket.get("lot_size", 1)) * int(ticket.get("lots", 1))
    return round(per_unit * qty, 2)