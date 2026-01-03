import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.db.models_intent import ExecutionIntent


def create_execution_intent(
    db: Session,
    *,
    run_id: int,
    strategy: str,
    underlying: str,
    ticket: dict,
    ttl_seconds: int = 120,
):
    intent = ExecutionIntent(
        run_id=run_id,
        intent_id=str(uuid.uuid4()),
        strategy=strategy,
        underlying=underlying,
        ticket=ticket,
        expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds),
    )

    db.add(intent)
    db.commit()
    db.refresh(intent)

    return intent
