from sqlalchemy.orm import Session
from app.db.models import StrategyRun


def get_recent_strategy_runs(
    db: Session,
    limit: int = 50,
):
    return (
        db.query(StrategyRun)
        .order_by(StrategyRun.id.desc())
        .limit(limit)
        .all()
    )
