from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import cast

from app.db.session import SessionLocal
from app.db.intent_repo import create_execution_intent
from app.db.models import StrategyRun
from app.db.models_intent import ExecutionIntent

from app.core.risk.trade_limit import check_daily_trade_limit
from app.core.risk.system_guard import is_trading_enabled

router = APIRouter(prefix="/intent", tags=["Execution Intent"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/create")
def create_intent(run_id: int, db: Session = Depends(get_db)):
    # 🔒 Manual kill switch
    if not is_trading_enabled(db):
        raise HTTPException(
            status_code=403,
            detail="Trading is disabled by system kill switch",
        )

    run = db.query(StrategyRun).filter(StrategyRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Strategy run not found")

    # SQLAlchemy-safe boolean check
    if run.approved is not True:
        raise HTTPException(status_code=400, detail="Strategy not approved")

    if run.ticket is None:
        raise HTTPException(
            status_code=400,
            detail="No executable ticket available for this run",
        )

    # 🔒 Daily trade limit guard
    if check_daily_trade_limit(db):
        raise HTTPException(
            status_code=429,
            detail="Daily trade limit reached",
        )

    intent = create_execution_intent(
        db=db,
        run_id=cast(int, run.id),
        strategy=str(run.strategy),
        underlying=str(run.underlying),
        ticket=run.ticket,
        tp=1500.0,    # TODO: make configurable
        sl=-2000.0,   # TODO: make configurable
    )

    return {
        "intent_id": intent.intent_id,
        "status": intent.status,
        "expires_at": intent.expires_at,
    }


@router.get("/{intent_id}")
def get_intent_status(intent_id: str, db: Session = Depends(get_db)):
    """
    Fetch current status of an execution intent.
    SAFE: Read-only, no side effects.
    """
    intent = (
        db.query(ExecutionIntent)
        .filter(ExecutionIntent.intent_id == intent_id)
        .first()
    )

    if intent is None:
        raise HTTPException(status_code=404, detail="Intent not found")

    return {
        "intent_id": intent.intent_id,
        "run_id": intent.run_id,
        "strategy": intent.strategy,
        "underlying": intent.underlying,
        "status": intent.status,
        "execution": intent.execution_result,
        "created_at": intent.created_at,
        "expires_at": intent.expires_at,
    }
