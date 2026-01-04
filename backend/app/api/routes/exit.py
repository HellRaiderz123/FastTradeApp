import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import cast

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent
from app.core.execution.paper import PaperExecutionAdapter
from app.core.execution.zerodha import ZerodhaExecutionAdapter
from app.core.utils.time import now_ist
from app.core.broker.zerodha.client import get_kite_client

router = APIRouter(prefix="/exit", tags=["Exit"])

EXECUTION_MODE = os.getenv("EXECUTION_MODE") 


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/manual/{intent_id}")
def manual_exit(intent_id: str, db: Session = Depends(get_db)):
    intent = (
        db.query(ExecutionIntent)
        .filter(ExecutionIntent.intent_id == intent_id)
        .first()
    )

    if intent is None:
        raise HTTPException(status_code=404, detail="Intent not found")

    if intent.status != "EXECUTED":  # type: ignore
        raise HTTPException(
            status_code=400,
            detail=f"Cannot exit intent in status {intent.status}",
        )

    # ✅ Adapter selection
    if EXECUTION_MODE == "PAPER":
        executor = PaperExecutionAdapter()
    else:
        kite = get_kite_client()
        executor = ZerodhaExecutionAdapter(kite_client=kite, dry_run=True)
    exit_result = executor.exit(intent)

   # ✅ Step-7 compliant finalization
    final_pnl = intent.unrealized_pnl

    intent.status = "CLOSED"                 # type: ignore
    intent.closed_at = now_ist()              # type: ignore
    intent.execution_result = exit_result # type: ignore
    intent.pnl = final_pnl
    intent.unrealized_pnl = None              # type: ignore # 🔥 REQUIRED

    db.commit()
    db.refresh(intent)  

    return {
        "intent_id": intent.intent_id,
        "status": intent.status,
        "closed_at": intent.closed_at,
        "final_pnl": intent.pnl,
        "mode": exit_result.get("mode"),
    }