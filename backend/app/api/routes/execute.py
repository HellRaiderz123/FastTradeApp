from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from typing import Dict, Any, cast as typing_cast, Optional
from datetime import date
from pydantic import BaseModel

from app.db.session import SessionLocal
from app.db.intent_query import get_intent_by_id
from app.core.execution.factory import get_execution_adapter
from app.core.utils.time import now_ist
from app.core.execution.credit import compute_entry_credit_total
from app.core.broker.zerodha.client import get_kite_client
from app.core.risk.risk_limits_config import get_risk_limits
from app.core.execution.mode import get_execution_mode
from app.db.models_intent import ExecutionIntent
from app.db.models import DailyCapital
from app.services.notifications import NotificationService
from app.db.intent_repo import create_execution_intent

# Phase 2: Circuit breaker + drawdown
from app.core.risk.circuit_breaker import CircuitBreaker, CircuitBreakerTripped
from app.core.risk.drawdown_tracker import DrawdownTracker
from app.core.risk.cost_calculator import calculate_costs_from_intent, format_cost_breakdown

router = APIRouter(prefix="/execute", tags=["Execution"])


class DirectTicketRequest(BaseModel):
    underlying: str
    strategy: str
    ticket: Dict[str, Any]
    tp: Optional[float] = None
    sl: Optional[float] = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _resolve_capital(db: Session) -> float:
    """
    Fetch live capital from Zerodha. Falls back to most recent daily_capital record.
    Raises 503 if neither is available (prevents trading with wrong capital).
    """
    try:
        kite = get_kite_client()
        margins = kite.margins()
        return float(margins["equity"]["available"]["live_balance"])
    except Exception:
        last_record = (
            db.query(DailyCapital)
            .order_by(DailyCapital.trade_date.desc())
            .first()
        )
        if last_record and last_record.closing_capital:
            return float(last_record.closing_capital)

    raise HTTPException(
        status_code=503,
        detail=(
            "Cannot determine capital — Zerodha API unavailable and no historical "
            "capital found. Record your capital via POST /account/daily-capital first."
        ),
    )


@router.post("/paper/{intent_id}")
def execute_paper(
    intent_id: str,
    idempotency_key: str = Header(...),
    db: Session = Depends(get_db),
):
    notifications = NotificationService(db)
    intent = get_intent_by_id(db, intent_id)

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

    if expires_at < now_ist():  # type: ignore
        raise HTTPException(status_code=400, detail="Intent expired")

    if intent.status != "CONFIRMED":  # type: ignore
        raise HTTPException(status_code=400, detail="Invalid intent state")

    # ── 1. Resolve capital ──────────────────────────────────────────────────
    capital = _resolve_capital(db)

    # ── 2. Drawdown check ───────────────────────────────────────────────────
    dd_tracker = DrawdownTracker(db, capital)
    dd_status = dd_tracker.get_status()
    if dd_status.trading_paused:
        raise HTTPException(
            status_code=403,
            detail=f"DRAWDOWN HALT: {dd_status.message}",
        )

    # ── 3. Circuit breaker — all checks including per-underlying ────────────
    cb = CircuitBreaker(db, capital)
    try:
        cb.check_all(underlying=intent.underlying)
    except CircuitBreakerTripped as e:
        # Notify on breach (best-effort)
        try:
            notifications.notify_pnl_threshold(
                daily_pnl=0.0,
                daily_pnl_pct=0.0,
                capital=capital,
                threshold_type="circuit_break",
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=403,
            detail=f"CIRCUIT BREAKER: {e.reason} — {e.detail}",
        )

    # ── 4. Adjust lot count for drawdown zone ───────────────────────────────
    ticket = intent.ticket_dict
    original_lots = ticket.get("lots", 1)
    adjusted_lots = dd_tracker.get_adjusted_lots(requested_lots=original_lots)

    if adjusted_lots < original_lots:
        # Mutate ticket with reduced lots (mark JSON dirty so SQLAlchemy persists it)
        ticket = dict(ticket)
        ticket["lots"] = adjusted_lots
        intent.ticket = ticket  # type: ignore

    # ── 5. Pre-trade cost estimate (logged, not blocking) ───────────────────
    try:
        costs = calculate_costs_from_intent(intent)
        import logging
        logging.getLogger(__name__).info(
            f"💸 Pre-trade cost estimate for {intent_id}: {format_cost_breakdown(costs)}"
        )
    except Exception:
        pass  # never block on cost calculation errors

    # ── 6. Execute ──────────────────────────────────────────────────────────
    intent.status = "EXECUTING"  # type: ignore
    db.commit()

    mode = get_execution_mode()
    executor = get_execution_adapter(mode)

    try:
        result = executor.execute(intent)
    except Exception as exec_err:
        intent.status = "CONFIRMED"  # type: ignore
        db.commit()
        try:
            notifications.notify_trade_failed(
                strategy_name=intent.strategy or intent.underlying or "Unknown",
                reason=str(exec_err),
                error_details={"intent_id": intent_id},
            )
        except Exception:
            pass
        raise

    # ── 7. Persist result ───────────────────────────────────────────────────
    intent.status = "EXECUTED"  # type: ignore
    intent.executed = True  # type: ignore
    intent.execution_result = result  # type: ignore

    entry_credit = result.get("entry_credit")
    if entry_credit is None:
        entry_credit = compute_entry_credit_total(intent.ticket)
    intent.entry_credit = entry_credit  # pyright: ignore[reportAttributeAccessIssue]

    # Initialize pnl to 0.0 so MTM updates have a valid baseline (avoids NULL → 0 confusion)
    if intent.pnl is None:  # type: ignore
        intent.pnl = 0.0  # type: ignore

    margin_required = result.get("margin_required")
    if margin_required is not None:
        intent.margin_required = margin_required  # pyright: ignore[reportAttributeAccessIssue]

    # Persist leg prices (JSON mutation may not auto-persist)
    try:
        ticket = intent.ticket or {}
        intent.ticket = dict(ticket)
    except Exception:
        pass

    intent.last_mtm_at = now_ist()  # type: ignore

    db.commit()

    # ── 8. Post-trade cost record (actual charges) ──────────────────────────
    trade_cost_summary = {}
    try:
        actual_costs = calculate_costs_from_intent(intent)
        trade_cost_summary = {
            "total_charges": actual_costs.total_charges,
            "effective_drag_pct": actual_costs.effective_drag_pct,
            "breakdown": format_cost_breakdown(actual_costs),
        }
    except Exception:
        pass

    # Fire success notification (best-effort)
    try:
        notifications.notify_trade_executed(
            strategy_name=intent.strategy or intent.underlying or "Strategy",
            underlying=intent.underlying or "N/A",
            trade_details={
                "entry_credit": entry_credit,
                "legs": (intent.ticket if isinstance(intent.ticket, dict) else {}).get("legs", []),
                "mode": get_execution_mode(),
                "intent_id": intent.intent_id,
                "lots_adjusted": adjusted_lots != original_lots,
                "original_lots": original_lots,
                "executed_lots": adjusted_lots,
            },
        )
    except Exception:
        pass

    return {
        "intent_id": intent.intent_id,
        "status": intent.status,
        "execution": result,
        "risk": {
            "drawdown_zone": dd_status.zone,
            "lots_requested": original_lots,
            "lots_executed": adjusted_lots,
        },
        "costs": trade_cost_summary,
    }


@router.post("/direct-ticket")
def execute_direct_ticket(
    req: DirectTicketRequest,
    db: Session = Depends(get_db),
):
    """
    Execute a raw ticket directly — used by Hedge, Adjust, and Add-to-Position
    from the Positions page. Bypasses strategy run creation; creates an intent
    in CONFIRMED state and executes it immediately.
    """
    from app.core.risk.system_guard import is_trading_enabled
    from app.core.market.expiry import get_next_weekly_expiry_from_kite
    from datetime import timedelta

    if not is_trading_enabled(db):
        raise HTTPException(status_code=403, detail="Trading is disabled by system kill switch")

    # Resolve expiry for the intent record
    try:
        expiry = get_next_weekly_expiry_from_kite(req.underlying)
    except Exception:
        expiry = None

    # Create intent directly in CONFIRMED state (no strategy run needed)
    intent = ExecutionIntent(
        intent_id=f"DIRECT-{now_ist().strftime('%Y%m%d%H%M%S')}-{req.strategy[:6].upper()}",
        strategy=req.strategy,
        underlying=req.underlying,
        ticket=req.ticket,
        expiry=str(expiry) if expiry else None,
        status="CONFIRMED",
        executed=False,
        tp=req.tp,
        sl=req.sl,
        pnl=0.0,
        expires_at=now_ist() + timedelta(minutes=5),
    )
    db.add(intent)
    db.commit()
    db.refresh(intent)

    # Execute immediately
    mode = get_execution_mode()
    executor = get_execution_adapter(mode)

    try:
        result = executor.execute(intent)
    except Exception as exc:
        db.delete(intent)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Execution failed: {exc}")

    intent.status = "EXECUTED"
    intent.executed = True
    intent.execution_result = result
    entry_credit = result.get("entry_credit") or compute_entry_credit_total(req.ticket)
    intent.entry_credit = entry_credit
    margin_required = result.get("margin_required")
    if margin_required is not None:
        intent.margin_required = margin_required
    intent.last_mtm_at = now_ist()
    db.commit()

    return {
        "intent_id": intent.intent_id,
        "status": "EXECUTED",
        "execution": result,
    }
