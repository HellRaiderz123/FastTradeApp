from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.intent_repo import create_execution_intent
from app.db.models import StrategyRun

from typing import Any, Dict, cast

router = APIRouter(prefix="/intent", tags=["Execution Intent"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/create")
def create_intent(run_id: int, db: Session = Depends(get_db)):
    run = db.query(StrategyRun).filter(StrategyRun.id == run_id).first()

    if run is None:
        raise HTTPException(status_code=404, detail="Strategy run not found")

    # IMPORTANT: explicit boolean check (SQLAlchemy-safe)
    if run.approved is not True:
        raise HTTPException(status_code=400, detail="Strategy not approved")

    if run.ticket is None:
        raise HTTPException(
            status_code=400,
            detail="No executable ticket available for this run",
        )

    intent = create_execution_intent(
        db=db,
        run_id=cast(int, run.id),
        strategy=str(run.strategy),
        underlying=str(run.underlying),
        ticket=cast(Dict[str, Any], run.ticket),
    )


    return {
        "intent_id": intent.intent_id,
        "status": intent.status,
        "expires_at": intent.expires_at,
    }
