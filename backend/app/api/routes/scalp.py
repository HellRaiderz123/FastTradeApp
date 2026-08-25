"""
scalp.py - API routes for scalp paper trading
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import SessionLocal
from app.core.scalp.scalp_paper_trader import (
    get_scalp_stats,
    get_recent_trades,
    run_scalp_cycle,
    scan_for_scalp_signals,
    export_trades_csv,
    SCALP_CONFIG,
)

router = APIRouter(prefix="/scalp", tags=["Scalp Trading"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/stats")
def scalp_stats(
    days: int = Query(30, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """Get scalp trading statistics and win rate analysis."""
    return get_scalp_stats(db, days=days)


@router.get("/trades")
def scalp_trades(
    limit: int = Query(50, description="Number of trades to return"),
    db: Session = Depends(get_db)
):
    """Get recent scalp trades."""
    return get_recent_trades(db, limit=limit)


@router.get("/signals")
def scalp_signals(db: Session = Depends(get_db)):
    """Get current scalp signals (without executing)."""
    signals = scan_for_scalp_signals(db)
    return {
        "count": len(signals),
        "signals": [
            {
                "underlying": s["underlying"],
                "signal_type": s["signal"].get("signal"),
                "confidence": s["signal"].get("confidence"),
                "reason": s["signal"].get("reason"),
                "scalp_ready": s["signal"].get("scalp_ready"),
                "indicators": s["signal"].get("indicators"),
            }
            for s in signals
        ]
    }


@router.post("/run")
def run_scalp(db: Session = Depends(get_db)):
    """Manually trigger one scalp trading cycle."""
    result = run_scalp_cycle(db)
    return result


@router.get("/config")
def scalp_config():
    """Get current scalp trading configuration."""
    return SCALP_CONFIG


@router.post("/export")
def export_scalp_trades(
    days: int = Query(30, description="Number of days to export"),
    db: Session = Depends(get_db)
):
    """Export scalp trades to CSV file."""
    filepath = export_trades_csv(db, days=days)
    return {"success": True, "filepath": filepath}
