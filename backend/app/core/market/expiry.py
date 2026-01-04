from datetime import date, timedelta

def get_next_weekly_expiry(today: date | None = None) -> date:
    """
    Returns next Thursday expiry.
    """
    today = today or date.today()
    days_ahead = (1 - today.weekday()) % 7  # Tuesday = 1
    expiry = today + timedelta(days=days_ahead)
    
    # If today is Tuesday and market already closed, move to next week
    if days_ahead == 0:
        expiry = expiry + timedelta(days=7)

    return expiry

def format_zerodha_expiry(expiry: date) -> str:
    """
    2026-01-25 → 26JAN
    """
    return expiry.strftime("%y%b").upper()

from datetime import date, timedelta


from datetime import date, timedelta

# NSE weekly expiry mapping
WEEKLY_EXPIRY_WEEKDAY = {
    "NIFTY": 1,        # Tuesday
    "FINNIFTY": 1,     # Tuesday
    "BANKNIFTY": 2,    # Wednesday
    "MIDCPNIFTY": 0,   # Monday (verify when trading)
}


def get_current_weekly_expiry(underlying: str) -> date:
    """
    Returns next weekly expiry date for the given underlying.
    """
    today = date.today()
    weekday_today = today.weekday()  # Monday=0

    expiry_weekday = WEEKLY_EXPIRY_WEEKDAY.get(underlying)
    if expiry_weekday is None:
        raise ValueError(f"No weekly expiry rule defined for {underlying}")

    days_ahead = (expiry_weekday - weekday_today) % 7
    expiry = today + timedelta(days=days_ahead)

    # If today is expiry day but market already closed,
    # you may want next week's expiry (optional enhancement)
    return expiry

