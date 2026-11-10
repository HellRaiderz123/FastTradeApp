from datetime import date, timedelta
import logging

import pandas as pd

logger = logging.getLogger(__name__)


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


def get_next_weekly_expiry_from_kite(underlying: str = "NIFTY", skip_monthly: bool = True) -> date:
    """
    Get the next valid expiry from broker instruments data.
    For INDMoney: reads nearest expiry from instruments cache (monthly only).
    For Zerodha: reads from NFO instruments (weekly + monthly).
    Falls back to naive weekday calculation if broker data unavailable.
    """
    try:
        from app.core.broker.registry import get_active_broker
        broker = get_active_broker()

        if broker == "INDMONEY":
            return _get_next_expiry_indmoney(underlying)

        instruments = None
        if broker == "ZERODHA":
            from app.core.broker.zerodha.instruments import load_instruments
            instruments = load_instruments("NFO")

        if instruments is not None and not instruments.empty:
            today = date.today()
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
            future_expiries = sorted(e for e in expiries if e >= today)

            if future_expiries:
                first = future_expiries[0]
                if first == today:
                    from datetime import datetime
                    try:
                        from zoneinfo import ZoneInfo
                        now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
                    except Exception:
                        from datetime import timezone
                        now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
                    market_close = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
                    if now_ist >= market_close and len(future_expiries) > 1:
                        first = future_expiries[1]
                return first

    except Exception as e:
        logger.warning("Failed to load broker expiries for %s: %s — using naive calc", underlying, e)

    return get_current_weekly_expiry(underlying)


def _get_next_expiry_indmoney(underlying: str) -> date:
    """
    Return the nearest future expiry for an underlying from the INDstocks
    instruments cache. Falls back to naive weekly calc if cache is empty.
    """
    try:
        from app.core.broker.indstocks.market_data import _instruments_cache
        cache = _instruments_cache()
        today = date.today()
        prefix = f"{underlying.upper()}|"
        expiries = sorted(
            date.fromisoformat(k.split("|")[1])
            for k in cache
            if k.startswith(prefix) and "|" in k
            and k.split("|")[1] not in ("0", "")
            and k.count("|") == 3
        )
        future = [e for e in expiries if e >= today]
        if future:
            logger.info("INDMoney expiry for %s: %s (from cache)", underlying, future[0])
            return future[0]
    except Exception as e:
        logger.warning("INDMoney expiry lookup failed for %s: %s", underlying, e)
    return get_current_weekly_expiry(underlying)

def get_next_weekly_expiry(today: date | None = None) -> date:
    """
    Returns next Thursday expiry (NIFTY default).
    """
    today = today or date.today()
    days_ahead = (3 - today.weekday()) % 7  # Thursday = 3
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)

def _is_last_weekday_of_month(expiry: date) -> bool:
    """Return True if expiry is the last occurrence of its weekday in the month."""
    return (expiry + timedelta(days=7)).month != expiry.month


# Zerodha single-char month codes for weekly expiry symbols
_WEEKLY_MONTH_CODE = {
    1: "1", 2: "2", 3: "3", 4: "4", 5: "5",
    6: "6", 7: "7", 8: "8", 9: "9",
    10: "O", 11: "N", 12: "D",
}


def format_zerodha_expiry(expiry: date) -> str:
    """
    Format expiry date for Zerodha symbol construction.

    Monthly: 2026-01-29 → 26JAN
    Weekly:  2026-02-10 → 26210   (YY + single-char-month + DD)
    Weekly:  2026-10-06 → 26O06   (Oct → 'O', Nov → 'N', Dec → 'D')
    """
    if _is_last_weekday_of_month(expiry):
        return expiry.strftime("%y%b").upper()

    year = expiry.year % 100
    month_code = _WEEKLY_MONTH_CODE[expiry.month]
    return f"{year}{month_code}{expiry.day:02d}"


# NSE weekly expiry mapping (Python weekday: Mon=0 … Sun=6)
WEEKLY_EXPIRY_WEEKDAY = {
    "NIFTY": 3,        # Thursday
    "FINNIFTY": 2,     # Wednesday (moved from Tuesday post-2024 restructure)
    "BANKNIFTY": 3,    # Thursday (moved from Wednesday post-2024 restructure)
    "MIDCPNIFTY": 1,   # Tuesday
}


def get_current_weekly_expiry(underlying: str) -> date:
    """
    Returns next WEEKLY expiry date for the given underlying.

    Weekly expiry days (post-2024 NSE restructure):
    - NIFTY:      Thursday
    - FINNIFTY:   Wednesday
    - BANKNIFTY:  Thursday
    - MIDCPNIFTY: Tuesday
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

