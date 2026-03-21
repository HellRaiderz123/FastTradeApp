from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.db.session import SessionLocal
from app.core.exit.broker_reconcile import reconcile_broker_positions
from app.db.models_intent import ExecutionIntent

router = APIRouter(prefix="/reconcile", tags=["Reconciliation"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/run")
def run_reconciliation(db: Session = Depends(get_db)):
    """Trigger broker reconciliation — closes stale positions that are squared off at Zerodha."""
    closed_ids = reconcile_broker_positions(db, force=True)
    return {
        "status": "ok",
        "closed_count": len(closed_ids),
        "closed_ids": closed_ids,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/status")
def get_reconciliation_status(db: Session = Depends(get_db)):
    """Return open EXECUTED intents vs broker-closed ones for discrepancy view."""
    open_intents = (
        db.query(ExecutionIntent)
        .filter(
            ExecutionIntent.status == "EXECUTED",
            ExecutionIntent.closed_at.is_(None),
        )
        .order_by(ExecutionIntent.created_at.desc())
        .limit(100)
        .all()
    )

    broker_closed = (
        db.query(ExecutionIntent)
        .filter(ExecutionIntent.exit_reason == "BROKER_CLOSED")
        .order_by(ExecutionIntent.closed_at.desc())
        .limit(50)
        .all()
    )

    def fmt(intent: ExecutionIntent):
        mode = ""
        if isinstance(intent.execution_result, dict):
            mode = str(intent.execution_result.get("mode", ""))
        return {
            "intent_id": intent.intent_id,
            "strategy": intent.strategy,
            "underlying": intent.underlying,
            "status": intent.status,
            "mode": mode,
            "pnl": intent.pnl,
            "created_at": intent.created_at.isoformat() if intent.created_at else None,
            "closed_at": intent.closed_at.isoformat() if intent.closed_at else None,
            "exit_reason": intent.exit_reason,
        }

    return {
        "open_intents": [fmt(i) for i in open_intents],
        "broker_closed_log": [fmt(i) for i in broker_closed],
        "open_count": len(open_intents),
        "broker_closed_count": len(broker_closed),
    }
