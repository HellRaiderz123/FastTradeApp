from datetime import date
from typing import Optional
from sqlalchemy.orm import Session

from app.db.models_intent import ExecutionIntent
from app.core.risk.risk_limits_config import RiskLimits, DEFAULT_RISK_LIMITS, get_risk_limits


def check_daily_trade_limit(
    db: Session,
    risk_config: Optional[RiskLimits] = None,
) -> bool:
    """
    Check if daily trade limit has been exceeded.
    
    Only counts successfully executed trades (executed=True).
    Failed or pending intents are not counted towards the limit.
    
    Args:
        db: Database session
        risk_config: RiskLimits configuration (uses default if None)
        
    Returns:
        True if limit exceeded, False if allowed
    """
    if risk_config is None:
        risk_config = get_risk_limits()
    
    today = date.today()

    count = (
        db.query(ExecutionIntent)
        .filter(
            ExecutionIntent.created_at >= today,
            ExecutionIntent.executed == True,  # Only count successful executions
        )
        .count()
    )

    return count >= risk_config.max_trades_per_day
