from datetime import date
from app.core.market.expiry import get_next_weekly_expiry, format_zerodha_expiry

def build_zerodha_option_symbol(
    *,
    underlying: str,
    strike: int,
    option_type: str,  # CE / PE
    expiry: date | None = None,
) -> str:
    expiry = expiry or get_next_weekly_expiry()
    expiry_code = format_zerodha_expiry(expiry)

    return f"{underlying}{expiry_code}{strike}{option_type}"
