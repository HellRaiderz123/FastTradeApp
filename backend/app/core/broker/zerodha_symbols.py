from datetime import date
from app.core.market.expiry import  format_zerodha_expiry
from datetime import date

def build_zerodha_option_symbol(
    *,
    underlying: str,
    strike: int,
    option_type: str,  # CE / PE
    expiry: date | None = None,
) -> str:
    if expiry is None:
        raise ValueError("Expiry must be explicitly provided")

    underlying = underlying.upper().replace(" ", "")

    option_type = option_type.upper()
    if option_type not in {"CE", "PE"}:
        raise ValueError(f"Invalid option type: {option_type}")

    expiry_code = format_zerodha_expiry(expiry)

    return f"{underlying}{expiry_code}{int(strike)}{option_type}"
