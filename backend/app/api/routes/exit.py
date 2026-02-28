from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent
from app.core.execution.paper import PaperExecutionAdapter
from app.core.execution.zerodha import ZerodhaExecutionAdapter
from app.core.utils.time import now_ist
from app.core.broker.zerodha.client import get_kite_client
from app.core.execution.mode import get_execution_mode, is_paper_mode, is_live_mode
from app.core.learning.signal_diagnostics import record_exit_outcome

router = APIRouter(prefix="/exit", tags=["Exit"])


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
    mode = get_execution_mode()
    if is_paper_mode(mode):
        executor = PaperExecutionAdapter()
    else:
        kite = get_kite_client()
        executor = ZerodhaExecutionAdapter(kite_client=kite, dry_run=not is_live_mode(mode))

    # 🔒 EXIT EXECUTION (single source of truth)
    exit_result = executor.exit(intent)

    # ✅ FINALIZE INTENT (IMMUTABLE)
    intent.status = "CLOSED"                    # type: ignore
    intent.exit_reason = "MANUAL"               # type: ignore
    intent.closed_at = now_ist()                # type: ignore
    intent.final_pnl = exit_result["final_pnl"] # type: ignore
    intent.pnl = exit_result["final_pnl"]       # type: ignore

    # 🔥 VERY IMPORTANT
    intent.unrealized_pnl = None                # type: ignore
    intent.execution_result = exit_result       # type: ignore

    try:
        record_exit_outcome(db, intent=intent, commit=False)
    except Exception:
        pass

    db.commit()
    db.refresh(intent)

    return {
        "intent_id": intent.intent_id,
        "status": intent.status,
        "closed_at": intent.closed_at,
        "final_pnl": intent.final_pnl,
        "exit_reason": intent.exit_reason,
        "mode": exit_result.get("mode"),
    }
