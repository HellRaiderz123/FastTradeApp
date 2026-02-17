"""
safety.py
---------
Phase 2: API routes for the safety dashboard widget.

Exposes circuit breaker status, drawdown status, expiry warnings,
and a pre-trade cost estimate — all in one place for the frontend.

Register in main.py:
    from app.api.routes import safety
    app.include_router(safety.router)
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from app.db.session import SessionLocal
from app.db.models import DailyCapital
from app.core.risk.circuit_breaker import CircuitBreaker
from app.core.risk.drawdown_tracker import DrawdownTracker
from app.core.risk.cost_calculator import calculate_trade_costs
from app.core.market.expiry_exit import get_expiry_warnings
from app.core.broker.zerodha.client import get_kite_client

router = APIRouter(prefix="/safety", tags=["Safety"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_capital(db: Session) -> float:
    """Attempt to resolve current capital; fall back to last daily record."""
    try:
        kite = get_kite_client()
        margins = kite.margins()
        return float(margins["equity"]["available"]["live_balance"])
    except Exception:
        last = (
            db.query(DailyCapital)
            .order_by(DailyCapital.trade_date.desc())
            .first()
        )
        if last and last.closing_capital:
            return float(last.closing_capital)
    return 0.0


@router.get("/status")
def get_safety_status(
    underlying: Optional[str] = Query(None, description="Check per-underlying limit for this symbol"),
    db: Session = Depends(get_db),
):
    """
    Full safety dashboard status.
    Returns circuit breaker state, drawdown zone, expiry warnings, and trade allowance.

    Used by the UI to show the Safety panel and block the Execute button.
    """
    capital = _get_capital(db)

    # Circuit breaker
    cb = CircuitBreaker(db, capital)
    cb_status = cb.get_status(underlying=underlying)

    # Drawdown
    dd = DrawdownTracker(db, capital)
    dd_status = dd.to_dict()

    # Expiry warnings
    warnings = get_expiry_warnings(db)
    critical_warnings = [w for w in warnings if w["urgency"] in ("CRITICAL", "EXPIRED")]

    # Overall trading allowed flag
    trading_allowed = (
        cb_status["trading_allowed"]
        and not dd_status["trading_paused"]
    )

    return {
        "trading_allowed": trading_allowed,
        "capital": round(capital, 2),
        "circuit_breaker": cb_status,
        "drawdown": dd_status,
        "expiry_warnings": warnings,
        "critical_expiry_count": len(critical_warnings),
    }


@router.get("/expiry-warnings")
def get_expiry_warning_list(db: Session = Depends(get_db)):
    """
    Return all positions with expiry within the next 24 hours.
    Urgency levels: CRITICAL (< 1h), HIGH (< 4h), MEDIUM (< 24h), EXPIRED.
    """
    return {"warnings": get_expiry_warnings(db)}


@router.get("/drawdown")
def get_drawdown_status(db: Session = Depends(get_db)):
    """Current drawdown status and position size scaling factor."""
    capital = _get_capital(db)
    dd = DrawdownTracker(db, capital)
    return dd.to_dict()


@router.get("/circuit-breaker")
def get_circuit_breaker_status(
    underlying: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Circuit breaker status — all check results."""
    capital = _get_capital(db)
    cb = CircuitBreaker(db, capital)
    return cb.get_status(underlying=underlying)


@router.post("/cost-estimate")
def estimate_trade_costs(
    legs: List[dict],
    db: Session = Depends(get_db),
):
    """
    Pre-trade cost estimate for a set of option legs.

    Request body: list of leg objects with keys:
        side (SELL/BUY), price (premium per unit), quantity (lot_size * lots)

    Example:
        POST /safety/cost-estimate
        [
          {"side": "SELL", "price": 120, "quantity": 50},
          {"side": "BUY",  "price":  60, "quantity": 50}
        ]
    """
    costs = calculate_trade_costs(legs)
    return {
        "total_charges": costs.total_charges,
        "effective_drag_pct": costs.effective_drag_pct,
        "breakdown": {
            "brokerage": costs.total_brokerage,
            "stt": costs.total_stt,
            "transaction_charges": costs.total_transaction,
            "gst": costs.total_gst,
            "stamp_duty": costs.total_stamp_duty,
            "sebi": costs.total_sebi,
        },
        "per_leg": [
            {
                "side": lc.side,
                "price": lc.price,
                "quantity": lc.quantity,
                "total": lc.total,
            }
            for lc in costs.legs
        ],
    }
