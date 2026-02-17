from typing import Optional
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date

from app.db.models_intent import ExecutionIntent
from app.core.risk.risk_limits_config import get_risk_limits



def check_portfolio_kill_switch(
    db: Session,
    capital: float,
    risk_profile: Optional[str] = None,  # Can override with 'conservative', 'balanced', 'aggressive'
) -> bool:
    """
    Returns True if trading must be HALTED.

    FIX: Only sums TODAY's PnL — not all-time cumulative.
    Using cumulative PnL masked daily losses behind historical profits,
    meaning the kill switch would never fire on a bad day.
    """
    # Get risk configuration based on profile
    risk_config = get_risk_limits(profile=risk_profile)

    today = date.today()

    total_pnl = (
        db.query(func.sum(ExecutionIntent.pnl))
        .filter(
            ExecutionIntent.status == "EXECUTED",
            ExecutionIntent.pnl.isnot(None),
            # Only consider trades created today
            cast(ExecutionIntent.created_at, Date) == today,
        )
        .scalar()
        or 0.0
    )

    loss_pct = abs(total_pnl) / capital * 100 if total_pnl < 0 else 0.0

    return loss_pct >= risk_config.max_portfolio_loss_pct