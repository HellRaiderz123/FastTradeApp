"""
Auto-Trader API Routes
-----------------------
Endpoints to configure, start/stop, and monitor the auto-trading engine.
"""

from datetime import time as dtime

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.db.session import SessionLocal
from app.db.models_auto_trader import AutoTraderConfig, AutoTraderLog
from app.core.auto_trader import (
    get_or_create_config,
    start_auto_trader,
    stop_auto_trader,
    pause_auto_trader,
    reset_daily_counters,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auto-trader", tags=["Auto Trader"])


def _validate_hhmm(value: str, field_name: str) -> str:
    try:
        parsed = dtime.fromisoformat(str(value))
        return f"{parsed.hour:02d}:{parsed.minute:02d}"
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}. Use HH:MM in 24-hour format.")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Config ──────────────────────────────────────────────────────────

@router.get("/config")
def get_config(db: Session = Depends(get_db)):
    """Get current auto-trader configuration."""
    cfg = get_or_create_config(db)
    import json as _json
    underlyings = cfg.underlyings
    if isinstance(underlyings, str):
        try:
            underlyings = _json.loads(underlyings)
        except Exception:
            underlyings = ["NIFTY"]
    return {
        "id": cfg.id,
        "underlyings": underlyings or ["NIFTY"],
        "capital": cfg.capital,
        "lots": cfg.lots,
        "risk_mode": cfg.risk_mode,
        "min_confidence": cfg.min_confidence,
        "max_open_positions": cfg.max_open_positions,
        "max_daily_loss": cfg.max_daily_loss,
        "default_tp": cfg.default_tp,
        "default_sl": cfg.default_sl,
        "trailing_sl_pct": cfg.trailing_sl_pct,
        "mode": cfg.mode,
        "enabled": cfg.enabled,
        "auto_exit_on_reversal": cfg.auto_exit_on_reversal,
        "auto_hedge_on_reversal": cfg.auto_hedge_on_reversal,
        "reversal_confidence_threshold": cfg.reversal_confidence_threshold,
        "scan_interval_sec": cfg.scan_interval_sec,
        "market_hours_only": cfg.market_hours_only,
        "entry_start_time": cfg.entry_start_time,
        "entry_end_time": cfg.entry_end_time,
        "use_ai_gate": getattr(cfg, "use_ai_gate", False),
        "ai_gate_min_confidence": getattr(cfg, "ai_gate_min_confidence", 0.65),
        "trade_stocks": getattr(cfg, "trade_stocks", False),
        "stock_symbols": getattr(cfg, "stock_symbols", []) or [],
        "status": cfg.status,
        "last_scan_at": cfg.last_scan_at,
        "error_message": cfg.error_message,
        "daily_pnl": cfg.daily_pnl,
        "daily_trades": cfg.daily_trades,
        "created_at": cfg.created_at,
        "updated_at": cfg.updated_at,
    }


@router.put("/config")
def update_config(
    underlyings: Optional[List[str]] = Body(None),
    capital: Optional[float] = Body(None),
    lots: Optional[int] = Body(None),
    risk_mode: Optional[str] = Body(None),
    min_confidence: Optional[float] = Body(None),
    max_open_positions: Optional[int] = Body(None),
    max_daily_loss: Optional[float] = Body(None),
    default_tp: Optional[float] = Body(None),
    default_sl: Optional[float] = Body(None),
    trailing_sl_pct: Optional[float] = Body(None),
    mode: Optional[str] = Body(None),
    auto_exit_on_reversal: Optional[bool] = Body(None),
    auto_hedge_on_reversal: Optional[bool] = Body(None),
    reversal_confidence_threshold: Optional[float] = Body(None),
    scan_interval_sec: Optional[int] = Body(None),
    market_hours_only: Optional[bool] = Body(None),
    entry_start_time: Optional[str] = Body(None),
    entry_end_time: Optional[str] = Body(None),
    use_ai_gate: Optional[bool] = Body(None),
    ai_gate_min_confidence: Optional[float] = Body(None),
    trade_stocks: Optional[bool] = Body(None),
    stock_symbols: Optional[List[str]] = Body(None),
    db: Session = Depends(get_db),
):
    """Update auto-trader configuration. Only provided fields are changed."""
    cfg = get_or_create_config(db)

    if underlyings is not None:
        cfg.underlyings = underlyings
    if capital is not None:
        cfg.capital = capital
    if lots is not None:
        cfg.lots = lots
    if risk_mode is not None:
        if risk_mode not in ("CONSERVATIVE", "BALANCED", "AGGRESSIVE"):
            raise HTTPException(status_code=400, detail="Invalid risk_mode")
        cfg.risk_mode = risk_mode
    if min_confidence is not None:
        cfg.min_confidence = min_confidence
    if max_open_positions is not None:
        cfg.max_open_positions = max_open_positions
    if max_daily_loss is not None:
        cfg.max_daily_loss = max_daily_loss
    if default_tp is not None:
        cfg.default_tp = default_tp if default_tp > 0 else None
    if default_sl is not None:
        cfg.default_sl = default_sl if default_sl < 0 else -abs(default_sl) if default_sl != 0 else None
    if trailing_sl_pct is not None:
        cfg.trailing_sl_pct = trailing_sl_pct
    if mode is not None:
        if mode not in ("PAPER", "DRY_RUN", "LIVE"):
            raise HTTPException(status_code=400, detail="Invalid mode. Use PAPER, DRY_RUN, or LIVE")
        if mode == "LIVE" and cfg.mode != "LIVE":
            logger.warning("⚠️ Auto-trader switched to LIVE mode!")
        cfg.mode = mode
    if auto_exit_on_reversal is not None:
        cfg.auto_exit_on_reversal = auto_exit_on_reversal
    if auto_hedge_on_reversal is not None:
        cfg.auto_hedge_on_reversal = auto_hedge_on_reversal
    if reversal_confidence_threshold is not None:
        cfg.reversal_confidence_threshold = reversal_confidence_threshold
    if scan_interval_sec is not None:
        cfg.scan_interval_sec = max(10, scan_interval_sec)  # minimum 10s
    if market_hours_only is not None:
        cfg.market_hours_only = market_hours_only
    if entry_start_time is not None:
        cfg.entry_start_time = _validate_hhmm(entry_start_time, "entry_start_time")
    if entry_end_time is not None:
        cfg.entry_end_time = _validate_hhmm(entry_end_time, "entry_end_time")
    if use_ai_gate is not None:
        cfg.use_ai_gate = use_ai_gate
    if ai_gate_min_confidence is not None:
        cfg.ai_gate_min_confidence = max(0.0, min(1.0, ai_gate_min_confidence))
    if trade_stocks is not None:
        cfg.trade_stocks = trade_stocks
    if stock_symbols is not None:
        cfg.stock_symbols = [s.strip().upper() for s in stock_symbols if s.strip()]

    effective_start = cfg.entry_start_time or "10:00"
    effective_end = cfg.entry_end_time or "15:15"
    if dtime.fromisoformat(effective_start) >= dtime.fromisoformat(effective_end):
        raise HTTPException(status_code=400, detail="entry_start_time must be earlier than entry_end_time")

    db.commit()
    db.refresh(cfg)

    return {"success": True, "config": {
        "underlyings": cfg.underlyings,
        "capital": cfg.capital,
        "mode": cfg.mode,
        "status": cfg.status,
        "enabled": cfg.enabled,
        "entry_start_time": cfg.entry_start_time,
        "entry_end_time": cfg.entry_end_time,
    }}


# ─── Control ─────────────────────────────────────────────────────────

@router.post("/start")
def start(db: Session = Depends(get_db)):
    """Start the auto-trader engine."""
    result = start_auto_trader(db)
    return result


@router.post("/stop")
def stop(db: Session = Depends(get_db)):
    """Stop the auto-trader engine."""
    result = stop_auto_trader(db)
    return result


@router.post("/pause")
def pause(db: Session = Depends(get_db)):
    """Pause scanning (positions still monitored for TP/SL)."""
    result = pause_auto_trader(db)
    return result


@router.post("/reset-daily")
def reset_daily(db: Session = Depends(get_db)):
    """Reset daily P&L and trade counters."""
    reset_daily_counters(db)
    return {"success": True, "message": "Daily counters reset"}


# ─── Status ──────────────────────────────────────────────────────────

@router.get("/status")
def get_status(db: Session = Depends(get_db)):
    """Get current auto-trader status summary."""
    cfg = get_or_create_config(db)

    # Count current open positions (exclude DIRECT_ZERODHA synced entries)
    from app.db.models_intent import ExecutionIntent
    open_count = (
        db.query(ExecutionIntent)
        .filter(
            ExecutionIntent.status == "EXECUTED",
            ExecutionIntent.closed_at.is_(None),
            ExecutionIntent.strategy != "DIRECT_ZERODHA",
        )
        .count()
    )

    # Today's trade count from logs
    from app.core.utils.time import now_ist
    from datetime import timedelta
    today_start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)

    today_entries = (
        db.query(AutoTraderLog)
        .filter(
            AutoTraderLog.action == "ENTRY",
            AutoTraderLog.created_at >= today_start,
        )
        .count()
    )

    today_exits = (
        db.query(AutoTraderLog)
        .filter(
            AutoTraderLog.action.in_(["REVERSAL_EXIT", "EXIT"]),
            AutoTraderLog.created_at >= today_start,
        )
        .count()
    )

    import json as _json
    underlyings = cfg.underlyings
    if isinstance(underlyings, str):
        try:
            underlyings = _json.loads(underlyings)
        except Exception:
            underlyings = ["NIFTY"]

    return {
        "status": cfg.status,
        "mode": cfg.mode,
        "enabled": cfg.enabled,
        "last_scan_at": cfg.last_scan_at,
        "error_message": cfg.error_message,
        "daily_pnl": cfg.daily_pnl or 0,
        "daily_trades": cfg.daily_trades or 0,
        "open_positions": open_count,
        "max_positions": cfg.max_open_positions,
        "today_entries": today_entries,
        "today_exits": today_exits,
        "underlyings": underlyings or ["NIFTY"],
        "capital": cfg.capital,
        "scan_interval_sec": cfg.scan_interval_sec,
        "entry_start_time": cfg.entry_start_time,
        "entry_end_time": cfg.entry_end_time,
    }


# ─── Logs ────────────────────────────────────────────────────────────

@router.get("/logs")
def get_logs(
    limit: int = 50,
    action: Optional[str] = None,
    underlying: Optional[str] = None,
    severity: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Get auto-trader action logs.
    Filter by action type, underlying, or severity.
    """
    query = db.query(AutoTraderLog).order_by(AutoTraderLog.created_at.desc())

    if action:
        query = query.filter(AutoTraderLog.action == action.upper())
    if underlying:
        query = query.filter(AutoTraderLog.underlying == underlying.upper())
    if severity:
        query = query.filter(AutoTraderLog.severity == severity.upper())

    logs = query.limit(min(limit, 200)).all()

    return {
        "logs": [
            {
                "id": log.id,
                "action": log.action,
                "underlying": log.underlying,
                "strategy": log.strategy,
                "reason": log.reason,
                "details": log.details,
                "intent_id": log.intent_id,
                "run_id": log.run_id,
                "pnl_impact": log.pnl_impact,
                "severity": log.severity,
                "created_at": log.created_at,
            }
            for log in logs
        ],
        "count": len(logs),
    }


@router.delete("/logs")
def clear_logs(db: Session = Depends(get_db)):
    """Clear all auto-trader logs."""
    deleted = db.query(AutoTraderLog).delete()
    db.commit()
    return {"deleted": deleted}
