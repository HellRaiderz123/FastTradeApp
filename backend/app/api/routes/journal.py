from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from app.db.session import SessionLocal
from app.db.queries import get_recent_strategy_runs
from app.db.models_intent import ExecutionIntent
from app.api.schemas.journal import StrategyRunOut, ExecutionIntentOut
from app.core.utils.time import now_ist

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

    # Best-effort MTM refresh for open paper positions.
    # (Uses Zerodha websocket ticks when available; REST fallback otherwise.)
    try:
        from app.core.execution.paper import PaperExecutionAdapter

        paper = PaperExecutionAdapter()
        changed = False
        for intent in intents:
            if intent is None:
                continue
            is_open = (intent.status == "EXECUTED") and (intent.closed_at is None)
            if not is_open:
                continue

            # Only compute MTM for paper intents (by convention stored in execution_result)
            mode = None
            if isinstance(intent.execution_result, dict):
                mode = intent.execution_result.get("mode")
            if mode and str(mode).upper() != "PAPER":
                continue

            mtm = paper.mtm(intent)
            intent.pnl = mtm
            intent.unrealized_pnl = mtm
            intent.last_mtm_at = now_ist()
            changed = True

        if changed:
            db.commit()
    except Exception:
        # Never fail the list endpoint due to MTM calculation.
        pass

    return intents
