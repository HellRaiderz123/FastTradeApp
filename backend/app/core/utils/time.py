from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    """
    Returns current time in IST (timezone-aware).
    """
    return datetime.now(tz=IST)
