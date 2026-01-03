from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from datetime import datetime
from typing import cast, Dict, Any

from app.db.session import SessionLocal
from app.db.intent_query import get_intent_by_id
from app.core.execution.paper import execute_paper_trade

router = APIRouter(prefix="/execute", tags=["Execution"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/paper/{intent_id}")
def execute_paper(
    intent_id: str,
    idempotency_key: str = Header(...),
    db: Session = Depends(get_db),
):
    intent = get_intent_by_id(db, intent_id)

    if not intent:
        raise HTTPException(status_code=404, detail="Intent not found")

    if cast(bool, intent.executed):
        return {
            "status": "ALREADY_EXECUTED",
            "result": intent.execution_result,
        }

    if cast(datetime, intent.expires_at) < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Intent expired")

    if cast(str, intent.status) != "CONFIRMED":
        raise HTTPException(status_code=400, detail="Invalid intent state")

    # ---- EXECUTION START ----
    cast(Any, intent).status = "EXECUTING"
    db.commit()

    ticket = cast(Dict[str, Any], intent.ticket)
    result = execute_paper_trade(ticket)

    cast(Any, intent).status = "EXECUTED"
    cast(Any, intent).executed = True
    cast(Any, intent).execution_result = result
    cast(Any, intent).avg_price = result.get("total_credit", 0.0)

    db.commit()

    return {
        "intent_id": intent.intent_id,
        "status": intent.status,
        "execution": result,
    }
