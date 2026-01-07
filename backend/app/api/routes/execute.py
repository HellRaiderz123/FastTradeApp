from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Dict, Any, cast

from app.db.session import SessionLocal
from app.db.intent_query import get_intent_by_id
from app.core.execution.paper import PaperExecutionAdapter
from app.core.execution.zerodha import ZerodhaExecutionAdapter
from app.core.utils.time import now_ist
from app.core.execution.credit import compute_entry_credit_total
from app.core.broker.zerodha.client import get_kite_client
from app.core.risk.kill_switch import check_portfolio_kill_switch
from app.core.execution.mode import get_execution_mode, is_paper_mode, is_live_mode, is_zerodha_dry_run

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

    # 🔹 Fetch real capital from Zerodha
    try:
        kite = get_kite_client()
        margins = kite.margins()
        capital = margins["equity"]["available"]
    except Exception:
        # Fallback to hardcoded value if API fails
        capital = 100000

    if check_portfolio_kill_switch(db, capital):
        raise HTTPException(
            status_code=403,
            detail="KILL SWITCH ACTIVE: Max portfolio loss exceeded",
        )

    if not intent:
        raise HTTPException(status_code=404, detail="Intent not found")

    if intent.executed is True:
        return {
            "status": "ALREADY_EXECUTED",
            "result": intent.execution_result,
        }

    expires_at = intent.expires_at
    if expires_at is None:
        raise HTTPException(status_code=400, detail="Intent has no expiry")

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=now_ist().tzinfo)

    if expires_at < now_ist(): # type: ignore
        raise HTTPException(status_code=400, detail="Intent expired")

    if intent.status != "CONFIRMED": # type: ignore
        raise HTTPException(status_code=400, detail="Invalid intent state")

    # ---- EXECUTION START ----
    intent.status = "EXECUTING" # type: ignore
    db.commit()

    mode = get_execution_mode()
    if is_paper_mode(mode):
        executor = PaperExecutionAdapter()
    else:
        kite = get_kite_client()
        executor = ZerodhaExecutionAdapter(kite_client=kite, dry_run=not is_live_mode(mode))

    try:
        result = executor.execute(intent)
    except Exception:
        intent.status = "CONFIRMED" # type: ignore
        db.commit()
        raise

    # ---- EXECUTION COMPLETE ----
    intent.status = "EXECUTED" # type: ignore
    intent.executed = True # type: ignore
    intent.execution_result = result # type: ignore
    entry_credit = result.get("entry_credit")
    if entry_credit is None:
        entry_credit = compute_entry_credit_total(intent.ticket)
    intent.entry_credit = entry_credit # pyright: ignore[reportAttributeAccessIssue]
    intent.last_mtm_at = now_ist() # type: ignore
    

    db.commit()

    return {
        "intent_id": intent.intent_id,
        "status": intent.status,
        "execution": result,
    }
