import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.db.models_intent import ExecutionIntent
from app.core.utils.time import now_ist


def create_execution_intent(
    db: Session,
    *,
    run_id: int,
    strategy: str,
    underlying: str,
    ticket: dict,
    tp: float | None = None,
    sl: float | None = None,
    ttl_seconds: int = 120,
):

    intent = ExecutionIntent(
        run_id=run_id,
        intent_id=str(uuid.uuid4()),
        strategy=strategy,
        underlying=underlying,
        ticket=ticket,
        tp=tp,
        sl=sl,
        expires_at=now_ist() + timedelta(seconds=ttl_seconds),
    )


    db.add(intent)
    db.commit()
    db.refresh(intent)

    return intent
