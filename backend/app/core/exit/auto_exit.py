import os
from datetime import timedelta
from sqlalchemy.orm import Session

from app.db.models_intent import ExecutionIntent
from app.core.utils.time import now_ist
from app.core.execution.mode import get_execution_mode
from app.core.execution.factory import get_execution_adapter
from app.services.notifications import NotificationService
from app.core.learning.signal_diagnostics import record_exit_outcome
import logging

logger = logging.getLogger(__name__)

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
        )
        .all()
    )

    exited = []

    execution_mode = get_execution_mode()
    executor = get_execution_adapter(execution_mode)

    notifications = NotificationService(db)

    now = now_ist()

    for intent in intents:
        reason = None
        current_pnl = intent.pnl or 0.0

        # Update max unrealized PnL (track highest profit)
        max_pnl = getattr(intent, 'max_unrealized_pnl', None) or 0.0
        if current_pnl > max_pnl:
            intent.max_unrealized_pnl = current_pnl  # type: ignore
            max_pnl = current_pnl

        # --- Fix 2: Exit at 50% of max profit for credit spreads ---
        entry_credit = intent.entry_credit or 0.0
        strategy = (intent.strategy or "").upper()
        is_credit_spread = strategy in ("BULL_PUT", "BEAR_CALL", "IRON_CONDOR", "SHORT_STRADDLE", "SHORT_STRANGLE")
        if is_credit_spread and entry_credit > 0 and current_pnl >= entry_credit * 0.5:
            reason = "PROFIT_50PCT"

        # --- Fix 6: Time-based exit (1 day before expiry if profitable) ---
        if not reason and intent.expiry and current_pnl > 0:
            try:
                from datetime import date as _date
                expiry_str = str(intent.expiry)
                expiry_date = _date.fromisoformat(expiry_str)
                if now.date() >= expiry_date - timedelta(days=1):
                    reason = "PRE_EXPIRY_EXIT"
            except (ValueError, TypeError):
                pass

        # Check TP
        if not reason and intent.tp is not None and current_pnl >= intent.tp:  # type: ignore
            reason = "TP_HIT"

        # Check SL
        elif not reason and intent.sl is not None and current_pnl <= intent.sl:  # type: ignore
            reason = "SL_HIT"

        # Check trailing stop only if trailing_sl_pct is configured
        elif (
            not reason
            and intent.trailing_sl_pct is not None  # type: ignore
            and intent.trailing_sl_pct > 0
            and max_pnl > 0
            and current_pnl < (max_pnl * (1 - intent.trailing_sl_pct / 100))  # type: ignore
        ):
            reason = "TRAILING_SL_HIT"

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

        try:
            record_exit_outcome(db, intent=intent, commit=False)
            logger.info(f"📊 Recorded exit outcome for intent {intent.intent_id}")
        except Exception as e:
            logger.error(f"❌ Failed to record exit outcome for {intent.intent_id}: {e}", exc_info=True)

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
            elif reason == "TRAILING_SL_HIT":
                notifications.notify_trailing_sl_hit(
                    strategy_name=intent.strategy or intent.underlying or "Strategy",
                    pnl=final_pnl,
                    pnl_pct=(final_pnl / (intent.entry_credit or 1)) * 100 if intent.entry_credit else 0.0,
                )
        except Exception:
            pass

        exited.append(intent.intent_id)

    db.commit()
    return exited
