from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.db.models_intent import ExecutionIntent
from app.core.risk.risk_limits_config import RiskLimits, DEFAULT_RISK_LIMITS, get_risk_limits


def check_daily_trade_limit(
    db: Session,
    risk_config: Optional[RiskLimits] = None,
) -> bool:
    if risk_config is None:
        risk_config = get_risk_limits()

    # Start of today in IST (UTC+5:30) as UTC for DB comparison
    from app.core.utils.time import now_ist
    now = now_ist()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    count = (
        db.query(ExecutionIntent)
        .filter(
            ExecutionIntent.status == "EXECUTED",
            ExecutionIntent.created_at >= today_start,
        )
        .count()
    )

    return count >= risk_config.max_trades_per_day
