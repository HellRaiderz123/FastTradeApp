"""
expiry_exit.py
--------------
Phase 2 Safety Feature — Expiry-Day Auto-Exit.

On option expiry day, all open option positions MUST be exited before
3:15 PM IST. Failing to do so risks:
  - OTM options expiring worthless (slippage at last minute)
  - ITM options leading to physical/cash settlement surprises
  - Options leg becoming illiquid near expiry

This module provides:
  1. run_expiry_day_exit()  — force-exits all open positions on expiry day
  2. is_expiry_day()        — returns True if any open intent expires today
  3. get_expiry_warnings()  — returns list of positions with upcoming expiry (24h, 4h, 1h)

Integration:
  Add _expiry_day_exit_check() to scheduler.py as a new cron job that runs
  every minute between 9:15 AM and 3:20 PM on weekdays.

  In scheduler.py, add:
      from app.core.market.expiry_exit import _expiry_day_exit_job
      ...
      def start_expiry_exit_scheduler():
          scheduler.add_job(
              func=_expiry_day_exit_job,
              trigger="cron",
              day_of_week="mon-fri",
              hour="9-15",
              minute="*",
              id="expiry_exit_job",
              replace_existing=True,
              max_instances=1,
          )
"""

import logging
from datetime import date, datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.utils.time import now_ist
from app.db.models_intent import ExecutionIntent
from app.db.session import SessionLocal
from app.core.execution.factory import get_execution_adapter
from app.core.execution.mode import get_execution_mode
from app.services.notifications import NotificationService
from app.core.learning.signal_diagnostics import record_exit_outcome

logger = logging.getLogger(__name__)

# Force-exit this many minutes before market close on expiry day
# 3:30 PM close → force exit at 3:15 PM (15 min buffer)
EXPIRY_EXIT_CUTOFF_HOUR: int = 15
EXPIRY_EXIT_CUTOFF_MINUTE: int = 15


def _parse_expiry(expiry_str: str) -> Optional[date]:
    """Parse expiry string to date. Handles YYYY-MM-DD and DD-Mon-YYYY formats."""
    if not expiry_str:
        return None
    formats = ["%Y-%m-%d", "%d-%b-%Y", "%d-%b-%y", "%Y/%m/%d"]
    for fmt in formats:
        try:
            return datetime.strptime(expiry_str, fmt).date()
        except ValueError:
            continue
    logger.warning(f"expiry_exit: could not parse expiry '{expiry_str}'")
    return None


def get_open_positions_expiring_on(db: Session, target_date: date) -> List[ExecutionIntent]:
    """Return all EXECUTED intents whose expiry matches target_date."""
    all_open = (
        db.query(ExecutionIntent)
        .filter(ExecutionIntent.status == "EXECUTED")
        .all()
    )
    return [
        intent for intent in all_open
        if intent.expiry and _parse_expiry(str(intent.expiry)) == target_date
    ]


def is_expiry_day(db: Session) -> bool:
    """Return True if any open position expires today."""
    today = date.today()
    return len(get_open_positions_expiring_on(db, today)) > 0


def get_expiry_warnings(db: Session) -> List[dict]:
    """
    Return warnings for positions expiring within the next 24 hours.
    Each entry includes urgency level: 'CRITICAL' (< 1h), 'HIGH' (< 4h), 'MEDIUM' (< 24h).
    """
    now = now_ist()
    all_open = (
        db.query(ExecutionIntent)
        .filter(ExecutionIntent.status == "EXECUTED")
        .all()
    )

    warnings = []
    for intent in all_open:
        if not intent.expiry:
            continue
        expiry_date = _parse_expiry(str(intent.expiry))
        if not expiry_date:
            continue

        # Expiry happens at 3:30 PM on expiry day
        expiry_dt = datetime(
            expiry_date.year, expiry_date.month, expiry_date.day,
            15, 30, 0,
            tzinfo=now.tzinfo,
        )
        time_left = expiry_dt - now

        if time_left.total_seconds() < 0:
            urgency = "EXPIRED"
        elif time_left.total_seconds() < 3600:
            urgency = "CRITICAL"       # < 1 hour
        elif time_left.total_seconds() < 4 * 3600:
            urgency = "HIGH"           # < 4 hours
        elif time_left.total_seconds() < 24 * 3600:
            urgency = "MEDIUM"         # < 24 hours
        else:
            continue  # not in warning window

        hours_left = time_left.total_seconds() / 3600

        warnings.append({
            "intent_id": intent.intent_id,
            "underlying": intent.underlying,
            "strategy": intent.strategy,
            "expiry": str(intent.expiry),
            "expiry_dt": expiry_dt.isoformat(),
            "hours_left": round(hours_left, 1),
            "urgency": urgency,
            "pnl": intent.pnl,
            "message": (
                f"{intent.underlying} ({intent.strategy}) expires in "
                f"{hours_left:.1f}h — exit recommended"
                if urgency != "EXPIRED"
                else f"{intent.underlying} ({intent.strategy}) may have already expired!"
            ),
        })

    # Sort by urgency: CRITICAL → HIGH → MEDIUM → EXPIRED
    urgency_order = {"CRITICAL": 0, "EXPIRED": 1, "HIGH": 2, "MEDIUM": 3}
    warnings.sort(key=lambda w: urgency_order.get(w["urgency"], 99))
    return warnings


def run_expiry_day_exit(db: Session) -> List[str]:
    """
    Force-exit all open positions that expire today.
    Called at EXPIRY_EXIT_CUTOFF_HOUR:EXPIRY_EXIT_CUTOFF_MINUTE on expiry days.

    Returns list of intent_ids that were exited.
    """
    today = date.today()
    expiring_today = get_open_positions_expiring_on(db, today)

    if not expiring_today:
        return []

    logger.info(
        f"⏰ Expiry-day exit: {len(expiring_today)} position(s) expire today. "
        "Force-exiting before 3:15 PM cutoff."
    )

    execution_mode = get_execution_mode()
    executor = get_execution_adapter(execution_mode)

    notifications = NotificationService(db)
    exited = []

    for intent in expiring_today:
        try:
            exit_result = executor.exit(intent)
            intent.status = "CLOSED"              # type: ignore
            intent.exit_reason = "EXPIRY_DAY_EXIT"  # type: ignore
            intent.closed_at = now_ist()          # type: ignore
            final_pnl = exit_result.get("final_pnl", intent.pnl)
            intent.pnl = final_pnl                # type: ignore
            intent.execution_result = exit_result  # type: ignore

            try:
                record_exit_outcome(db, intent=intent, commit=False)
                logger.info(f"📊 Recorded exit outcome for intent {intent.intent_id}")
            except Exception as e:
                logger.error(f"❌ Failed to record exit outcome for {intent.intent_id}: {e}", exc_info=True)

            exited.append(intent.intent_id)
            logger.info(
                f"✅ Expiry exit: {intent.intent_id} "
                f"({intent.underlying}, {intent.strategy}) "
                f"PnL: ₹{final_pnl:,.2f}"
            )

            # Notify
            try:
                notifications.notify_trade_executed(
                    strategy_name=f"[EXPIRY EXIT] {intent.strategy or intent.underlying}",
                    underlying=intent.underlying or "N/A",
                    trade_details={
                        "reason": "EXPIRY_DAY_EXIT",
                        "final_pnl": final_pnl,
                        "intent_id": intent.intent_id,
                    },
                )
            except Exception:
                pass

        except Exception as e:
            logger.error(
                f"❌ Expiry exit failed for {intent.intent_id}: {e}",
                exc_info=True,
            )

    db.commit()
    return exited


def _expiry_day_exit_job():
    """
    APScheduler job function — called every minute during market hours.
    Only triggers the force-exit when clock passes the cutoff time.
    """
    now = now_ist()

    # Only act on weekdays
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return

    # Only trigger at or after cutoff
    cutoff = now.replace(
        hour=EXPIRY_EXIT_CUTOFF_HOUR,
        minute=EXPIRY_EXIT_CUTOFF_MINUTE,
        second=0,
        microsecond=0,
    )
    if now < cutoff:
        return

    db = SessionLocal()
    try:
        exited = run_expiry_day_exit(db)
        if exited:
            logger.info(
                f"⏰ Expiry-day exit job: closed {len(exited)} position(s): {exited}"
            )
    except Exception:
        logger.exception("❌ Expiry-day exit job failed")
    finally:
        db.close()
