import os
from sqlalchemy.orm import Session

from app.db.models_intent import ExecutionIntent
from app.core.utils.time import now_ist
from app.core.execution.paper import PaperExecutionAdapter
from app.core.execution.zerodha import ZerodhaExecutionAdapter
from app.core.execution.mode import get_execution_mode, is_live_mode, is_paper_mode
from app.core.broker.zerodha.client import get_kite_client
from app.services.notifications import NotificationService


def run_auto_exit(db: Session):
    """
    Adapter-based TP / SL auto exit.
    SAFE:
    - Paper exits simulate
    - Zerodha exits are DRY-RUN only
    """

    intents = (
        db.query(ExecutionIntent)
        .filter(
            ExecutionIntent.status == "EXECUTED",
            ExecutionIntent.pnl.isnot(None),
        )
        .all()
    )

    exited = []

    execution_mode = get_execution_mode()

    if is_paper_mode(execution_mode):
        executor = PaperExecutionAdapter()
    else:
        kite = get_kite_client()
        executor = ZerodhaExecutionAdapter(
            kite_client=kite,
            dry_run=not is_live_mode(execution_mode),
        )

    notifications = NotificationService(db)

    for intent in intents:
        reason = None

        if intent.tp is not None and intent.pnl >= intent.tp: # type: ignore
            reason = "TP_HIT"

        elif intent.sl is not None and intent.pnl <= intent.sl: # type: ignore
            reason = "SL_HIT"

        if not reason:
            continue

        # ---- EXIT ----
        exit_result = executor.exit(intent)

        intent.status = "CLOSED"          # type: ignore
        intent.exit_reason = reason       # type: ignore
        intent.closed_at = now_ist()      # type: ignore

        # Safe PnL assignment
        final_pnl = exit_result.get("final_pnl", intent.pnl)
        intent.pnl = final_pnl

        intent.execution_result = exit_result # type: ignore

        # Notify based on exit reason (best-effort)
        try:
            if reason == "TP_HIT":
                notifications.notify_tp_hit(
                    strategy_name=intent.strategy or intent.underlying or "Strategy",
                    pnl=final_pnl,
                    pnl_pct=(final_pnl / (intent.entry_credit or 1)) * 100 if intent.entry_credit else 0.0,
                )
            elif reason == "SL_HIT":
                notifications.notify_sl_hit(
                    strategy_name=intent.strategy or intent.underlying or "Strategy",
                    pnl=final_pnl,
                    pnl_pct=(final_pnl / (intent.entry_credit or 1)) * 100 if intent.entry_credit else 0.0,
                )
        except Exception:
            pass

        exited.append(intent.intent_id)

    db.commit()
    return exited
