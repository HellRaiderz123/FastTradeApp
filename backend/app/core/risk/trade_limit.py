from datetime import date
from sqlalchemy.orm import Session

from app.db.models_intent import ExecutionIntent


def check_daily_trade_limit(db: Session) -> bool:
    today = date.today()

    count = (
        db.query(ExecutionIntent)
        .filter(
            ExecutionIntent.created_at >= today,
        )
        .count()
    )

    return count >= 3
