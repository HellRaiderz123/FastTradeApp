"""
auto_trader.py
--------------
Core Auto-Trader Engine — runs on a scheduler, scans TA signals,
opens/exits/hedges positions automatically based on configuration.

Modes:
    PAPER      — simulate trades with LTP (no real orders)
    DRY_RUN    — Zerodha dry-run (logs but doesn't fire)
    LIVE       — real Zerodha orders (requires explicit opt-in)

Flow per scan:
1. Load config → check enabled + market hours
2. For each underlying, run TA signal → decide strategy
3. Check open positions for reversals → auto-exit or hedge
4. If no conflicting position, create new intent + execute
5. Log everything to auto_trader_log
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, time as dtime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.utils.time import now_ist
from app.db.session import SessionLocal
from app.db.models_auto_trader import AutoTraderConfig, AutoTraderLog
from app.db.models_intent import ExecutionIntent
from app.db.intent_repo import create_execution_intent
from app.core.signals.signals import generate_signal
from app.core.strategies.option_spread_15m.context import build_market_context
from app.core.strategies.option_spread_15m.decision import decide_strategy
from app.core.strategies.option_spread_15m.engine import run_option_spread
from app.core.position_advisor import advise_position, STRATEGY_BIAS
from app.core.risk.tp_sl_calculator import (
    calculate_tp_sl_from_ticket,
    get_risk_percentage_from_mode,
    get_risk_percentage_from_settings,
)
from app.core.execution.paper import PaperExecutionAdapter
from app.core.execution.zerodha import ZerodhaExecutionAdapter
from app.core.execution.mode import normalize_execution_mode, is_live_mode, is_paper_mode
from app.core.broker.zerodha.client import get_kite_client
from app.core.learning.signal_diagnostics import record_entry_snapshot, record_exit_outcome

logger = logging.getLogger(__name__)

# ─── Market-hours check ──────────────────────────────────────────────

MARKET_OPEN = dtime(9, 16)
MARKET_CLOSE = dtime(15, 15)

# Prevent concurrent scans from creating duplicate positions
_scan_lock = threading.Lock()


def _is_market_open() -> bool:
    """Return True if Indian markets are currently open (9:16–15:15 IST, Mon-Fri)."""
    now = now_ist()
    if now.weekday() >= 5:  # Saturday / Sunday
        return False
    t = now.time()
    return MARKET_OPEN <= t <= MARKET_CLOSE


# ─── Helpers ──────────────────────────────────────────────────────────

def _log(db: Session, config_id: int, **kwargs):
    """Write an AutoTraderLog entry."""
    entry = AutoTraderLog(**kwargs)
    db.add(entry)
    try:
        db.commit()

        try:
            record_entry_snapshot(
                db,
                intent=intent,
                engine_result=engine_result,
            )
        except Exception:
            pass
    except Exception:
        db.rollback()


def _get_executor(mode: str):
    """Instantiate the right execution adapter for the given mode."""
    norm = normalize_execution_mode(mode)
    if is_paper_mode(norm):
        return PaperExecutionAdapter()
    kite = get_kite_client()
    return ZerodhaExecutionAdapter(
        kite_client=kite,
        dry_run=not is_live_mode(norm),
    )


def _open_positions_for(db: Session, underlying: str) -> List[ExecutionIntent]:
    """Return EXECUTED intents for a given underlying."""
    return (
        db.query(ExecutionIntent)
        .filter(
            ExecutionIntent.underlying == underlying,
            ExecutionIntent.status == "EXECUTED",
        )
        .all()
    )


# ─── Main scan job ────────────────────────────────────────────────────

def auto_trader_scan():
    """
    Top-level function called by the APScheduler job.
    Opens its own DB session, runs one full scan cycle, then closes.
    Uses a lock to prevent overlapping scans from creating duplicates.
    """
    if not _scan_lock.acquire(blocking=False):
        logger.debug("Auto-trader scan skipped — previous scan still running")
        return

    db = SessionLocal()
    try:
        _run_scan(db)
    except Exception as exc:
        logger.exception("Auto-trader scan failed: %s", exc)
        # Try to mark config as ERROR
        try:
            cfg = db.query(AutoTraderConfig).first()
            if cfg:
                cfg.status = "ERROR"
                cfg.error_message = str(exc)[:500]
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()
        _scan_lock.release()


def _run_scan(db: Session):
    """Core scan logic — runs inside a DB session."""

    cfg: Optional[AutoTraderConfig] = db.query(AutoTraderConfig).first()
    if cfg is None:
        return  # no config yet
    if not cfg.enabled or cfg.status not in ("RUNNING", "PAUSED"):
        return
    if cfg.status == "PAUSED":
        return

    # Market-hours guard
    if cfg.market_hours_only and not _is_market_open():
        return

    # ── Daily counter reset (new trading day) ─────────────────────
    now = now_ist()
    if cfg.last_scan_at:
        last_date = cfg.last_scan_at.date() if hasattr(cfg.last_scan_at, "date") else None
        if last_date and last_date < now.date():
            logger.info("Auto-trader: new trading day detected — resetting daily counters")
            cfg.daily_pnl = 0
            cfg.daily_trades = 0
            db.commit()

    # Daily loss guard
    if cfg.max_daily_loss and cfg.daily_pnl is not None:
        if cfg.daily_pnl <= -abs(cfg.max_daily_loss):
            if cfg.status != "PAUSED":
                cfg.status = "PAUSED"
                cfg.error_message = f"Daily loss limit reached (₹{cfg.daily_pnl:.0f})"
                _log(db, cfg.id,
                     action="STOP", reason="Daily loss limit reached",
                     details={"daily_pnl": cfg.daily_pnl, "limit": cfg.max_daily_loss},
                     severity="WARNING")
                db.commit()
            return

    underlyings: List[str] = cfg.underlyings or ["NIFTY"]

    # Get executor — fall back to Paper if Kite unavailable
    try:
        executor = _get_executor(cfg.mode or "PAPER")
    except Exception as exc:
        logger.warning("Auto-trader executor creation failed (%s), falling back to PAPER: %s", cfg.mode, exc)
        executor = PaperExecutionAdapter()
        _log(db, cfg.id,
             action="ERROR",
             reason=f"Executor init failed ({cfg.mode}), using Paper fallback: {str(exc)[:150]}",
             severity="WARNING")

    for underlying in underlyings:
        try:
            _scan_underlying(db, cfg, underlying, executor)
        except Exception as exc:
            logger.warning("Auto-trader scan error for %s: %s", underlying, exc)
            _log(db, cfg.id,
                 action="ERROR", underlying=underlying,
                 reason=str(exc)[:300], severity="ERROR")

    cfg.last_scan_at = now_ist()
    db.commit()


# ─── Per-underlying scan ──────────────────────────────────────────────

def _scan_underlying(db: Session, cfg: AutoTraderConfig, underlying: str, executor):
    """
    For one underlying:
    1. Check open positions for TA reversal → exit/hedge
    2. If slot available, evaluate new entry
    """

    # ── Step 1: Reversal monitoring on existing positions ──────────
    open_intents = _open_positions_for(db, underlying)

    for intent in open_intents:
        strategy = intent.strategy
        if not strategy:
            continue

        # Use position_advisor to check conflict
        advice = advise_position(
            strategy=strategy,
            underlying=underlying,
            db=db,
            pnl=intent.pnl or 0.0,
            entry_credit=intent.entry_credit or 0.0,
            min_confidence=cfg.reversal_confidence_threshold or 65,
        )

        action = advice.get("action", "HOLD")
        severity = advice.get("severity", "NONE")
        confidence = advice.get("current_confidence", 0)

        # Act on HIGH severity signals OR MEDIUM severity with CONSIDER_EXIT action
        should_act = (
            (severity == "HIGH" and confidence >= (cfg.reversal_confidence_threshold or 65))
            or (severity == "MEDIUM" and action == "CONSIDER_EXIT")
        )

        if should_act:
            if cfg.auto_exit_on_reversal:
                _auto_exit_position(db, cfg, intent, executor, advice)
            elif cfg.auto_hedge_on_reversal:
                _auto_hedge_position(db, cfg, intent, underlying, advice)
            else:
                _log(db, cfg.id,
                     action="SKIP", underlying=underlying,
                     strategy=strategy, intent_id=intent.intent_id,
                     reason=f"Reversal detected but auto-action disabled: {advice.get('reason', '')}",
                     details=advice, severity="WARNING")
        elif severity in ("MEDIUM", "LOW") and action in ("WATCH", "HEDGE_SUGGESTED"):
            # Log for awareness but don't auto-act
            _log(db, cfg.id,
                 action="SCAN", underlying=underlying,
                 strategy=strategy, intent_id=intent.intent_id,
                 reason=f"{severity} severity watch: {advice.get('reason', '')}",
                 details=advice, severity="INFO")

    # ── Step 2: New entry evaluation ──────────────────────────────
    # Count only auto-trader-created positions (exclude DIRECT_ZERODHA synced)
    total_open = (
        db.query(ExecutionIntent)
        .filter(
            ExecutionIntent.status == "EXECUTED",
            ExecutionIntent.closed_at.is_(None),
            ExecutionIntent.strategy != "DIRECT_ZERODHA",
        )
        .count()
    )
    max_pos = cfg.max_open_positions or 3
    if total_open >= max_pos:
        _log(db, cfg.id,
             action="SKIP", underlying=underlying,
             reason=f"Position limit reached ({total_open}/{max_pos})",
             severity="INFO")
        return

    # Skip if we already have an auto-trader position for this underlying
    auto_intents = [i for i in open_intents if (i.strategy or "") != "DIRECT_ZERODHA"]
    if auto_intents:
        _log(db, cfg.id,
             action="SKIP", underlying=underlying,
             strategy=auto_intents[0].strategy,
             reason=f"Already have open {auto_intents[0].strategy} position for {underlying}",
             severity="INFO")
        return

    # Run full strategy engine
    payload = {
        "underlying": underlying,
        "use_ml": False,
        "min_confidence": cfg.min_confidence or 70,
        "risk_mode": cfg.risk_mode or "BALANCED",
        "lots": cfg.lots or 1,
        "capital": cfg.capital or 100000,
    }

    try:
        result = run_option_spread(db, payload)
    except Exception as exc:
        logger.warning("Auto-trader engine error for %s: %s", underlying, exc)
        _log(db, cfg.id,
             action="ERROR", underlying=underlying,
             reason=f"Engine error: {str(exc)[:200]}",
             severity="ERROR")
        return

    strategy = result.get("strategy", "NO_TRADE")
    approved = result.get("approved", False)
    ticket = result.get("ticket")

    # Log the scan result
    _log(db, cfg.id,
         action="SCAN", underlying=underlying,
         strategy=strategy,
         reason=result.get("reason", ""),
         details={
             "approved": approved,
             "confidence": result.get("signal", {}).get("confidence", 0),
             "market_mode": result.get("context", {}).get("market_mode", ""),
             "iv_regime": result.get("context", {}).get("iv_regime", ""),
         },
         run_id=result.get("run_id"),
         severity="INFO")

    if not approved or strategy == "NO_TRADE" or not ticket:
        return

    # ── Create intent + execute ───────────────────────────────────
    _auto_enter_position(db, cfg, underlying, strategy, ticket, result, executor)


# ─── Entry logic ──────────────────────────────────────────────────────

def _auto_enter_position(
    db: Session,
    cfg: AutoTraderConfig,
    underlying: str,
    strategy: str,
    ticket: dict,
    engine_result: dict,
    executor,
):
    """Create an ExecutionIntent and immediately execute it."""

    # Calculate TP/SL
    # 💡 Priority: Use database setting (Settings UI) over hardcoded profiles
    # This respects the "Risk Per Trade (%)" setting configured by the user
    try:
        risk_pct = get_risk_percentage_from_settings(db)
    except Exception:
        # Fallback to config risk_mode if DB unavailable
        risk_pct = get_risk_percentage_from_mode(cfg.risk_mode or "BALANCED")
    
    tp_sl = calculate_tp_sl_from_ticket(
        ticket=ticket,
        capital=cfg.capital or 100000,
        risk_percentage=risk_pct,
    )

    # Override with config defaults if set
    tp = cfg.default_tp if cfg.default_tp else tp_sl.get("tp")
    sl = cfg.default_sl if cfg.default_sl else tp_sl.get("sl")
    trailing = cfg.trailing_sl_pct if cfg.trailing_sl_pct else None

    # Get expiry from ticket
    expiry = ticket.get("expiry")

    intent = create_execution_intent(
        db=db,
        run_id=engine_result.get("run_id", 0),
        strategy=strategy,
        underlying=underlying,
        ticket=ticket,
        expiry=expiry,
        tp=tp,
        sl=sl,
        trailing_sl_pct=trailing,
        ttl_seconds=86400,  # 24h TTL for auto-trader entries
    )

    # Execute immediately
    try:
        exec_result = executor.execute(intent)
        intent.status = "EXECUTED"
        intent.execution_result = exec_result
        intent.entry_credit = exec_result.get("entry_credit", 0)

        # Force SQLAlchemy to detect in-place ticket mutations
        # (executor.execute stores leg prices + qty on ticket["legs"])
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(intent, "ticket")

        db.commit()

        _log(db, cfg.id,
             action="ENTRY", underlying=underlying,
             strategy=strategy, intent_id=intent.intent_id,
             run_id=engine_result.get("run_id"),
             reason=f"Auto-entry: {strategy} via TA signal",
             details={
                 "entry_credit": exec_result.get("entry_credit", 0),
                 "tp": tp, "sl": sl,
                 "mode": cfg.mode,
                 "confidence": engine_result.get("signal", {}).get("confidence", 0),
             },
             severity="SUCCESS")

        # Update daily counters
        cfg.daily_trades = (cfg.daily_trades or 0) + 1
        db.commit()

    except Exception as exc:
        intent.status = "FAILED"
        db.commit()
        logger.warning("Auto-trader execute failed for %s: %s", underlying, exc)
        _log(db, cfg.id,
             action="ERROR", underlying=underlying,
             strategy=strategy, intent_id=intent.intent_id,
             reason=f"Execution failed: {str(exc)[:200]}",
             severity="ERROR")


# ─── Reversal exit ────────────────────────────────────────────────────

def _auto_exit_position(
    db: Session,
    cfg: AutoTraderConfig,
    intent: ExecutionIntent,
    executor,
    advice: dict,
):
    """Exit a position due to TA reversal."""
    try:
        exit_result = executor.exit(intent)
        final_pnl = exit_result.get("final_pnl", intent.pnl or 0)

        intent.status = "CLOSED"
        intent.exit_reason = "AUTO_REVERSAL_EXIT"
        intent.closed_at = now_ist()
        intent.pnl = final_pnl
        intent.execution_result = exit_result
        db.commit()

        try:
            record_exit_outcome(db, intent=intent)
        except Exception:
            pass

        # Update daily P&L
        cfg.daily_pnl = (cfg.daily_pnl or 0) + (final_pnl or 0)
        db.commit()

        _log(db, cfg.id,
             action="REVERSAL_EXIT", underlying=intent.underlying,
             strategy=intent.strategy, intent_id=intent.intent_id,
             reason=advice.get("reason", "TA reversal detected"),
             details={
                 "advice": advice,
                 "final_pnl": final_pnl,
                 "mode": cfg.mode,
             },
             pnl_impact=final_pnl,
             severity="WARNING")

    except Exception as exc:
        logger.warning("Auto-exit failed for %s: %s", intent.intent_id, exc)
        _log(db, cfg.id,
             action="ERROR", underlying=intent.underlying,
             strategy=intent.strategy, intent_id=intent.intent_id,
             reason=f"Auto-exit failed: {str(exc)[:200]}",
             severity="ERROR")


# ─── Reversal hedge ──────────────────────────────────────────────────

def _auto_hedge_position(
    db: Session,
    cfg: AutoTraderConfig,
    intent: ExecutionIntent,
    underlying: str,
    advice: dict,
):
    """
    Instead of exiting, open a hedge position opposite to current.
    e.g., if we have BULL_PUT and TA flips bearish, open a BEAR_CALL to hedge.
    """
    current_strategy = intent.strategy or ""
    current_bias = STRATEGY_BIAS.get(current_strategy, "NEUTRAL")

    # Determine hedge strategy
    hedge_map = {
        "BULLISH": "BEAR_CALL",    # hedge a bull position with bear call
        "BEARISH": "BULL_PUT",     # hedge a bear position with bull put
    }
    hedge_strategy = hedge_map.get(current_bias)

    if not hedge_strategy:
        _log(db, cfg.id,
             action="SKIP", underlying=underlying,
             strategy=current_strategy, intent_id=intent.intent_id,
             reason=f"Cannot determine hedge for {current_strategy} (bias={current_bias})",
             severity="WARNING")
        return

    # Run engine to get the hedge ticket
    payload = {
        "underlying": underlying,
        "use_ml": False,
        "min_confidence": 50,  # lower threshold for hedges
        "risk_mode": "CONSERVATIVE",
        "lots": cfg.lots or 1,
        "capital": (cfg.capital or 100000) * 0.5,  # use half capital for hedge
    }

    try:
        result = run_option_spread(db, payload)
        ticket = result.get("ticket")
        if not ticket:
            _log(db, cfg.id,
                 action="SKIP", underlying=underlying,
                 strategy=hedge_strategy,
                 reason="Hedge engine returned no ticket",
                 details={"engine_result": result.get("reason", "")},
                 severity="WARNING")
            return

        executor = _get_executor(cfg.mode or "PAPER")
        _auto_enter_position(db, cfg, underlying, hedge_strategy, ticket, result, executor)

        _log(db, cfg.id,
             action="HEDGE", underlying=underlying,
             strategy=hedge_strategy, intent_id=intent.intent_id,
             reason=f"Auto-hedge against {current_strategy} reversal",
             details=advice,
             severity="WARNING")

    except Exception as exc:
        logger.warning("Auto-hedge failed for %s: %s", underlying, exc)
        _log(db, cfg.id,
             action="ERROR", underlying=underlying,
             reason=f"Auto-hedge failed: {str(exc)[:200]}",
             severity="ERROR")


# ─── Config management helpers ────────────────────────────────────────

def get_or_create_config(db: Session) -> AutoTraderConfig:
    """Get existing config or create a default one."""
    cfg = db.query(AutoTraderConfig).first()
    if cfg is None:
        cfg = AutoTraderConfig(
            underlyings=["NIFTY"],
            capital=100000,
            lots=1,
            risk_mode="BALANCED",
            min_confidence=70,
            max_open_positions=3,
            max_daily_loss=5000,
            mode="PAPER",
            enabled=False,
            status="STOPPED",
            auto_exit_on_reversal=True,
            auto_hedge_on_reversal=False,
            reversal_confidence_threshold=65,
            scan_interval_sec=30,
            market_hours_only=True,
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def start_auto_trader(db: Session) -> Dict[str, Any]:
    """Start the auto-trader engine."""
    cfg = get_or_create_config(db)
    cfg.enabled = True
    cfg.status = "RUNNING"
    cfg.error_message = None
    cfg.daily_pnl = 0
    cfg.daily_trades = 0
    db.commit()

    _log(db, cfg.id,
         action="START",
         reason=f"Auto-trader started in {cfg.mode} mode",
         details={"underlyings": cfg.underlyings, "capital": cfg.capital},
         severity="SUCCESS")

    # Ensure scheduler job exists
    _ensure_scheduler_job(cfg.scan_interval_sec or 30)

    return {"status": "RUNNING", "mode": cfg.mode}


def stop_auto_trader(db: Session) -> Dict[str, Any]:
    """Stop the auto-trader engine."""
    cfg = get_or_create_config(db)
    cfg.enabled = False
    cfg.status = "STOPPED"
    db.commit()

    _log(db, cfg.id,
         action="STOP",
         reason="Auto-trader stopped by user",
         severity="INFO")

    _remove_scheduler_job()

    return {"status": "STOPPED"}


def pause_auto_trader(db: Session) -> Dict[str, Any]:
    """Pause scanning. Open positions still monitored by auto_exit."""
    cfg = get_or_create_config(db)
    cfg.status = "PAUSED"
    db.commit()

    _log(db, cfg.id,
         action="STOP",
         reason="Auto-trader paused by user",
         severity="INFO")

    return {"status": "PAUSED"}


def reset_daily_counters(db: Session):
    """Reset daily PnL and trade count — call at start of day."""
    cfg = db.query(AutoTraderConfig).first()
    if cfg:
        cfg.daily_pnl = 0
        cfg.daily_trades = 0
        db.commit()


# ─── Scheduler integration ───────────────────────────────────────────

_JOB_ID = "auto_trader_scan"


def _ensure_scheduler_job(interval_sec: int = 30):
    """Add the auto-trader job to the global APScheduler if not already there."""
    from app.core.market.scheduler import scheduler

    if scheduler.get_job(_JOB_ID):
        scheduler.reschedule_job(
            _JOB_ID,
            trigger="interval",
            seconds=interval_sec,
        )
    else:
        scheduler.add_job(
            auto_trader_scan,
            "interval",
            seconds=interval_sec,
            id=_JOB_ID,
            replace_existing=True,
            max_instances=1,
        )
    logger.info("Auto-trader scheduler job active (every %ds)", interval_sec)


def _remove_scheduler_job():
    """Remove the auto-trader job from the scheduler."""
    from app.core.market.scheduler import scheduler
    if scheduler.get_job(_JOB_ID):
        scheduler.remove_job(_JOB_ID)
        logger.info("Auto-trader scheduler job removed")
