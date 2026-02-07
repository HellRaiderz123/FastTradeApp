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
    Monthly: 2026-01-29 → 26JAN
    Weekly:  2026-01-09 → 26JAN09
    """
    if _is_last_weekday_of_month(expiry):
        return expiry.strftime("%y%b").upper()
    return expiry.strftime("%y%b%d").upper()

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

