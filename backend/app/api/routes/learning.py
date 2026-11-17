"""
Learning API
POST /learning/reflect/{intent_id}   — trigger reflection for a specific trade
GET  /learning/reflections           — paginated list of all reflections
GET  /learning/patterns              — aggregated failure patterns
GET  /learning/diagnostics           — reuses existing signal_diagnostics
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import SessionLocal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/learning", tags=["learning"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/reflect/{intent_id}")
def trigger_reflection(intent_id: str, db: Session = Depends(get_db)):
    """Manually trigger a post-mortem reflection for a closed SL trade."""
    from app.db.models_signal_outcome import SignalOutcome
    from app.services.sl_reflection_engine import reflect_on_sl

    outcome = db.query(SignalOutcome).filter(SignalOutcome.intent_id == intent_id).first()
    if not outcome:
        raise HTTPException(status_code=404, detail="Trade outcome not found")

    if outcome.outcome != "LOSS":
        raise HTTPException(status_code=400, detail="Reflection only applies to LOSS trades")

    result = reflect_on_sl(
        db,
        intent_id=intent_id,
        symbol=outcome.underlying or "UNKNOWN",
        strategy=outcome.strategy or "UNKNOWN",
        pnl=float(outcome.pnl or 0),
        sl_time=outcome.exit_time or outcome.updated_at,
        signal_json=outcome.signal_json or {},
        context_json=outcome.context_json or {},
    )
    if result is None:
        return {"status": "already_reflected", "intent_id": intent_id}

    return {"status": "reflected", **result}


@router.get("/reflections")
def get_reflections(
    symbol: Optional[str] = Query(None),
    strategy: Optional[str] = Query(None),
    primary_cause: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Paginated list of SL reflections."""
    from app.db.models_sl_reflection import SLReflection

    q = db.query(SLReflection)
    if symbol:
        q = q.filter(SLReflection.symbol == symbol.upper())
    if strategy:
        q = q.filter(SLReflection.strategy == strategy.upper())
    if primary_cause:
        q = q.filter(SLReflection.primary_cause == primary_cause.upper())

    total = q.count()
    rows = q.order_by(SLReflection.reflected_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "data": [
            {
                "id": r.id,
                "intent_id": r.intent_id,
                "symbol": r.symbol,
                "strategy": r.strategy,
                "pnl": r.pnl,
                "primary_cause": r.primary_cause,
                "weights": {
                    "news": r.news_weight,
                    "technical": r.technical_weight,
                    "macro": r.macro_weight,
                    "iv": r.iv_weight,
                    "timing": r.timing_weight,
                },
                "entry_rsi": r.entry_rsi,
                "entry_vix": r.entry_vix,
                "entry_iv_regime": r.entry_iv_regime,
                "entry_market_mode": r.entry_market_mode,
                "news_filing_found": bool(r.news_filing_found),
                "news_sentiment": r.news_sentiment,
                "news_tags": [t for t in (r.news_tags or "").split(",") if t],
                "reflection_text": r.reflection_text,
                "reflected_at": r.reflected_at.isoformat() if r.reflected_at else None,
            }
            for r in rows
        ],
    }


@router.get("/patterns")
def get_failure_patterns(
    min_trades: int = Query(2, ge=1),
    db: Session = Depends(get_db),
):
    """Aggregated failure patterns from all SL reflections."""
    from app.services.sl_reflection_engine import get_failure_patterns
    patterns = get_failure_patterns(db, min_trades=min_trades)
    return {"patterns": patterns, "count": len(patterns)}


@router.get("/diagnostics")
def get_diagnostics(
    lookback_days: Optional[int] = Query(30, ge=1, le=365),
    limit: int = Query(200, ge=1, le=1000),
    underlying: Optional[str] = Query(None),
    strategy: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Signal diagnostics — reuses existing compute_signal_diagnostics."""
    from app.core.learning.signal_diagnostics import compute_signal_diagnostics
    return compute_signal_diagnostics(
        db,
        limit=limit,
        lookback_days=lookback_days,
        underlying=underlying,
        strategy=strategy,
    )
