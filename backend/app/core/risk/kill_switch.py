from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models_intent import ExecutionIntent
from app.core.strategies.option_spread_15m.risk import MAX_PORTFOLIO_LOSS_PCT


def check_portfolio_kill_switch(
    db: Session,
    capital: float,
) -> bool:
    """
    Returns True if trading must be HALTED.
    """

    total_pnl = (
        db.query(func.sum(ExecutionIntent.pnl))
        .filter(
            ExecutionIntent.status == "EXECUTED",
            ExecutionIntent.pnl.isnot(None),
        )
        .scalar()
        or 0.0
    )

    loss_pct = abs(total_pnl) / capital * 100 if total_pnl < 0 else 0.0

    return loss_pct >= MAX_PORTFOLIO_LOSS_PCT
