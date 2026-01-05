from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from app.db.session import SessionLocal
from app.db.queries import get_recent_strategy_runs
from app.db.models_intent import ExecutionIntent
from app.api.schemas.journal import StrategyRunOut, ExecutionIntentOut

router = APIRouter(prefix="/journal", tags=["Journal"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get(
    "/strategy-runs",
    response_model=List[StrategyRunOut],
)
def list_strategy_runs(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return get_recent_strategy_runs(db, limit=limit)


@router.get(
    "/execution-intents",
    response_model=List[ExecutionIntentOut],
)
def list_execution_intents(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    List recent execution intents (active or closed trades).
    
    Returns:
        List of execution intents ordered by most recent first.
    """
    intents = db.query(ExecutionIntent).order_by(ExecutionIntent.created_at.desc()).limit(limit).all()
    return intents
