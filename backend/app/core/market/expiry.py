from datetime import date, timedelta

import pandas as pd

def get_next_valid_expiry(instruments: pd.DataFrame, underlying: str):
    today = pd.Timestamp.today().date()

    expiries = (
        instruments[
            (instruments["name"] == underlying)
            & (instruments["segment"] == "NFO-OPT")
        ]["expiry"]
        .dropna()
        .drop_duplicates()
        .sort_values()
    )

    expiries = pd.to_datetime(expiries).dt.date
    future_expiries = expiries[expiries >= today]

    return future_expiries.iloc[0] if not future_expiries.empty else None

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

def _is_last_weekday_of_month(expiry: date) -> bool:
    """Return True if expiry is the last occurrence of its weekday in the month."""
    return (expiry + timedelta(days=7)).month != expiry.month


def format_zerodha_expiry(expiry: date) -> str:
    """
    Format expiry date for Zerodha symbol construction.
    
    Monthly: 2026-01-29 → 26JAN
    Weekly:  2026-02-10 → 26210  (YY + M + D, no zero-padding on month/day)
    Weekly:  2026-02-17 → 26217  
    Weekly:  2026-12-03 → 261203 (YY + M + D)
    """
    if _is_last_weekday_of_month(expiry):
        # Monthly format: YYMMMM (e.g., 26JAN)
        return expiry.strftime("%y%b").upper()
    
    # Weekly format: YYMD where single-digit month/day have NO zero padding
    # Feb 10, 2026 → 26 + 2 + 10 → 26210 (not 260210)
    year = expiry.year % 100  # Last 2 digits of year
    month = expiry.month      # Month as 1-12 (no zero padding)
    day = expiry.day          # Day as 1-31 (no zero padding)
    return f"{year}{month}{day}"


# NSE weekly expiry mapping
WEEKLY_EXPIRY_WEEKDAY = {
    "NIFTY": 1,        # Tuesday
    "FINNIFTY": 1,     # Tuesday
    "BANKNIFTY": 2,    # Wednesday
    "MIDCPNIFTY": 0,   # Monday (verify when trading)
}


def get_current_weekly_expiry(underlying: str) -> date:
    """
    Returns next WEEKLY expiry date for the given underlying (skips monthly expiries).
    
    Weekly expiry days:
    - NIFTY: Tuesday
    - FINNIFTY: Tuesday
    - BANKNIFTY: Wednesday
    - MIDCPNIFTY: Monday
    
    Note: Always returns at least the nearest expiry, even if it's monthly.
    """
    today = date.today()
    weekday_today = today.weekday()  # Monday=0

    expiry_weekday = WEEKLY_EXPIRY_WEEKDAY.get(underlying)
    if expiry_weekday is None:
        raise ValueError(f"No weekly expiry rule defined for {underlying}")

    days_ahead = (expiry_weekday - weekday_today) % 7
    
    # If today is the expiry day, check if market has closed
    if days_ahead == 0:
        from datetime import datetime, timezone
        try:
            from zoneinfo import ZoneInfo
            ist_tz = ZoneInfo("Asia/Kolkata")
        except:
            ist_tz = timezone(timedelta(hours=5, minutes=30))
        
        now_ist = datetime.now(ist_tz)
        market_close_time = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
        
        if now_ist >= market_close_time:
            # Market closed, skip to next week
            days_ahead = 7
        # else: days_ahead stays 0, meaning today is still valid
    
    expiry = today + timedelta(days=days_ahead)
    
    # If the calculated expiry is monthly (last occurrence of weekday in month),
    # check if we can skip to the next weekly expiry
    if _is_last_weekday_of_month(expiry) and days_ahead > 0:
        # Only skip monthly if it's not today's expiry
        expiry = expiry + timedelta(days=7)
    
    return expiry


def get_weekly_expiry_for_date(underlying: str, asof_date: date) -> date:
    """Return the weekly expiry date for a given underlying as-of a past date.

    Uses WEEKLY_EXPIRY_WEEKDAY mapping. Returns the next expiry date that is
    >= asof_date (including the same day).
    """
    underlying = (underlying or "").upper().strip()

    expiry_weekday = WEEKLY_EXPIRY_WEEKDAY.get(underlying)
    if expiry_weekday is None:
        raise ValueError(f"No weekly expiry rule defined for {underlying}")

    weekday_today = asof_date.weekday()  # Monday=0
    days_ahead = (expiry_weekday - weekday_today) % 7
    expiry = asof_date + timedelta(days=days_ahead)
    return expiry

