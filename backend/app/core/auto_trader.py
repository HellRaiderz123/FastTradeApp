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
from datetime import datetime, time as dtime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.utils.time import now_ist
from app.db.session import SessionLocal
from app.db.models_auto_trader import AutoTraderConfig, AutoTraderLog, ensure_auto_trader_schema
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
from app.core.execution.factory import get_execution_adapter
from app.core.execution.paper import PaperExecutionAdapter
from app.core.learning.signal_diagnostics import record_entry_snapshot, record_exit_outcome
from app.services.notifications import NotificationService

logger = logging.getLogger(__name__)


def _notify(db, method: str, *args, **kwargs):
    """Fire a NotificationService method, swallowing all errors."""
    try:
        svc = NotificationService(db)
        getattr(svc, method)(*args, **kwargs)
    except Exception as exc:
        logger.debug("Notification failed (%s): %s", method, exc)

# ─── Market-hours check ──────────────────────────────────────────────

MARKET_OPEN = dtime(9, 16)
MARKET_CLOSE = dtime(15, 15)
DEFAULT_ENTRY_START = "10:00"
DEFAULT_ENTRY_END = "15:15"

# Prevent concurrent scans from creating duplicate positions
_scan_lock = threading.Lock()


def _is_market_open() -> bool:
    """Return True if Indian markets are currently open (9:16–15:15 IST, Mon-Fri)."""
    now = now_ist()
    if now.weekday() >= 5:  # Saturday / Sunday
        return False
    t = now.time()
    return MARKET_OPEN <= t <= MARKET_CLOSE


def _parse_time_value(raw: Optional[str], fallback: dtime) -> dtime:
    if not raw:
        return fallback
    try:
        parsed = dtime.fromisoformat(str(raw))
        return dtime(parsed.hour, parsed.minute)
    except Exception:
        return fallback


def _entry_window_label(cfg: AutoTraderConfig) -> str:
    return f"{getattr(cfg, 'entry_start_time', None) or DEFAULT_ENTRY_START}-{getattr(cfg, 'entry_end_time', None) or DEFAULT_ENTRY_END}"


def _is_within_entry_window(cfg: AutoTraderConfig) -> bool:
    now = now_ist()
    if now.weekday() >= 5:
        return False

    start = _parse_time_value(getattr(cfg, "entry_start_time", None), dtime(10, 0))
    end = _parse_time_value(getattr(cfg, "entry_end_time", None), MARKET_CLOSE)
    current = now.time().replace(second=0, microsecond=0)

    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


# ─── Helpers ──────────────────────────────────────────────────────────

def _log(db: Session, config_id: int, **kwargs):
    """Write an AutoTraderLog entry."""
    entry = AutoTraderLog(**kwargs)
    db.add(entry)
    try:
        db.commit()
    except Exception:
        db.rollback()


def _get_executor(mode: str):
    """Instantiate the right execution adapter for the given mode."""
    return get_execution_adapter(mode)


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
                _notify(db, "notify_pnl_threshold",
                        cfg.daily_pnl, (cfg.daily_pnl / (cfg.capital or 100000)) * 100,
                        cfg.capital or 100000, "loss")
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

    # Stock universe scan (Tier 1 feature)
    if getattr(cfg, "trade_stocks", False):
        stock_symbols: List[str] = getattr(cfg, "stock_symbols", None) or []
        for sym in stock_symbols:
            try:
                _scan_stock(db, cfg, sym, executor)
            except Exception as exc:
                logger.warning("Auto-trader stock scan error for %s: %s", sym, exc)

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

        # ── SL / TP check against live MTM ────────────────────────
        if intent.sl is not None or intent.tp is not None:
            try:
                from app.core.execution.paper import PaperExecutionAdapter
                current_pnl = PaperExecutionAdapter().mtm(intent)
                intent.pnl = current_pnl
                db.commit()
                sl_hit = intent.sl is not None and current_pnl <= intent.sl
                tp_hit = intent.tp is not None and current_pnl >= intent.tp
                if sl_hit or tp_hit:
                    reason = "SL hit" if sl_hit else "TP hit"
                    _auto_exit_position(db, cfg, intent, executor, {"reason": reason})
                    continue
            except Exception as _e:
                logger.debug("SL/TP check failed for %s: %s", intent.intent_id, _e)

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
        # MEDIUM requires confidence >= threshold to avoid noisy exits on signal flicker
        should_act = (
            (severity == "HIGH" and confidence >= (cfg.reversal_confidence_threshold or 65))
            or (severity == "MEDIUM" and action == "CONSIDER_EXIT"
                and confidence >= (cfg.reversal_confidence_threshold or 65))
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

    # Re-query to avoid stale session cache — check for existing position for this underlying
    auto_intents = (
        db.query(ExecutionIntent)
        .filter(
            ExecutionIntent.underlying == underlying,
            ExecutionIntent.status == "EXECUTED",
            ExecutionIntent.closed_at.is_(None),
            ExecutionIntent.strategy != "DIRECT_ZERODHA",
        )
        .all()
    )
    if auto_intents:
        _log(db, cfg.id,
             action="SKIP", underlying=underlying,
             strategy=auto_intents[0].strategy,
             reason=f"Already have open {auto_intents[0].strategy} position for {underlying}",
             severity="INFO")
        return

    # Cooldown: don't re-enter within 15 min of a reversal exit on same underlying
    recent_exit = (
        db.query(ExecutionIntent)
        .filter(
            ExecutionIntent.underlying == underlying,
            ExecutionIntent.status == "CLOSED",
            ExecutionIntent.exit_reason == "AUTO_REVERSAL_EXIT",
            ExecutionIntent.closed_at >= now_ist() - timedelta(minutes=15),
        )
        .first()
    )
    if recent_exit:
        _log(db, cfg.id,
             action="SKIP", underlying=underlying,
             reason=f"Cooldown: reversal exit {recent_exit.intent_id} was <15min ago",
             severity="INFO")
        return

    if not _is_within_entry_window(cfg):
        _log(db, cfg.id,
             action="SKIP", underlying=underlying,
             reason=f"Outside fresh-entry window ({_entry_window_label(cfg)} IST)",
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

    # ── AI Gate (optional) ────────────────────────────────────────
    if getattr(cfg, "use_ai_gate", False):
        if not _ai_gate_allows_entry(db, cfg, underlying, strategy):
            return

    # ── Create intent + execute ───────────────────────────────────
    _auto_enter_position(db, cfg, underlying, strategy, ticket, result, executor)


# ─── AI Gate ─────────────────────────────────────────────────────────

def _ai_gate_allows_entry(
    db: Session,
    cfg: AutoTraderConfig,
    underlying: str,
    strategy: str,
) -> bool:
    """
    Check the latest AI pipeline decision for this underlying.
    Returns True only if the AI approved a BUY/SELL with sufficient confidence.
    Falls back to True (allow) if no AI decision exists yet.
    """
    try:
        from app.db.models_ai_decisions import AIDecision
        from sqlalchemy import desc

        row = (
            db.query(AIDecision)
            .filter(AIDecision.symbol == underlying)
            .order_by(desc(AIDecision.analysed_at))
            .first()
        )
        if row is None:
            # No AI analysis yet — allow entry (don't block on missing data)
            logger.debug("AI gate: no decision for %s, allowing entry", underlying)
            return True

        min_conf = float(getattr(cfg, "ai_gate_min_confidence", 0.65) or 0.65)
        ai_action = (row.action or "").upper()
        ai_conf = float(row.confidence or 0)
        execution_allowed = bool(row.execution_allowed)

        if not execution_allowed or ai_action not in ("BUY", "SELL") or ai_conf < min_conf:
            _log(db, cfg.id,
                 action="SKIP", underlying=underlying,
                 strategy=strategy,
                 reason=(
                     f"AI gate blocked: action={ai_action} conf={ai_conf:.2f} "
                     f"execution_allowed={execution_allowed} min_conf={min_conf:.2f}"
                 ),
                 severity="INFO")
            return False

        logger.info(
            "AI gate: %s approved for %s (action=%s conf=%.2f)",
            underlying, strategy, ai_action, ai_conf,
        )
        return True
    except Exception as exc:
        logger.warning("AI gate check failed for %s: %s — allowing entry", underlying, exc)
        return True  # fail-open


# ─── Stock scan ───────────────────────────────────────────────────────

def _scan_stock(db: Session, cfg: AutoTraderConfig, symbol: str, executor):
    """
    Run the momentum stock strategy for a single symbol.
    Creates an intent and executes if signal is strong enough.
    """
    open_for_symbol = _open_positions_for(db, symbol)
    auto_open = [i for i in open_for_symbol if (i.strategy or "") != "DIRECT_ZERODHA"]
    if auto_open:
        return  # already have a position

    total_open = (
        db.query(ExecutionIntent)
        .filter(
            ExecutionIntent.status == "EXECUTED",
            ExecutionIntent.closed_at.is_(None),
            ExecutionIntent.strategy != "DIRECT_ZERODHA",
        )
        .count()
    )
    if total_open >= (cfg.max_open_positions or 3):
        return

    if not _is_within_entry_window(cfg):
        return

    try:
        from app.core.signals.signals import generate_signal
        sig_dict = generate_signal(db=db, symbol=symbol, use_ml=False)
        confidence = float(sig_dict.get("confidence", 0))
        if confidence < (cfg.min_confidence or 70):
            return

        action = str(sig_dict.get("recommendation", "NO_TRADE")).upper()
        if action not in ("BUY", "SELL"):
            return

        # Build a minimal ticket compatible with _auto_enter_position
        from app.services.market_data import get_spot
        spot = get_spot(symbol)
        risk_pct = 2.0
        sl_price = spot * (1 - risk_pct / 100) if action == "BUY" else spot * (1 + risk_pct / 100)
        tp_price = spot * (1 + risk_pct * 1.5 / 100) if action == "BUY" else spot * (1 - risk_pct * 1.5 / 100)

        ticket = {
            "strategy": "STOCK_MOMENTUM",
            "underlying": symbol,
            "lot_size": 1,
            "lots": cfg.lots or 1,
            "legs": [{
                "side": action,
                "strike": spot,
                "type": "STOCK",
                "symbol": symbol,
                "price": spot,
            }],
            "stop_loss": sl_price,
            "take_profit": tp_price,
        }
        result = {
            "strategy": "STOCK_MOMENTUM",
            "approved": True,
            "signal": sig_dict,
            "context": {},
            "run_id": None,
        }
    except Exception as exc:
        logger.warning("Stock strategy error for %s: %s", symbol, exc)
        return

    # AI gate check for stocks too
    if getattr(cfg, "use_ai_gate", False):
        if not _ai_gate_allows_entry(db, cfg, symbol, "STOCK_MOMENTUM"):
            return

    _auto_enter_position(db, cfg, symbol, "STOCK_MOMENTUM", ticket, result, executor)


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
        intent.executed = True
        intent.execution_result = exec_result
        intent.entry_credit = exec_result.get("entry_credit", 0)
        intent.margin_required = exec_result.get("margin_required") or intent.margin_required

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
                 "margin_required": exec_result.get("margin_required"),
                 "tp": tp, "sl": sl,
                 "mode": cfg.mode,
                 "confidence": engine_result.get("signal", {}).get("confidence", 0),
             },
             severity="SUCCESS")

        try:
            record_entry_snapshot(
                db,
                intent=intent,
                engine_result=engine_result,
            )
        except Exception:
            pass

        _notify(db, "notify_trade_executed", strategy, underlying, {
            "entry_credit": exec_result.get("entry_credit", 0),
            "margin_required": exec_result.get("margin_required"),
            "tp": tp, "sl": sl,
            "mode": cfg.mode,
            "confidence": engine_result.get("signal", {}).get("confidence", 0),
            "legs": ticket.get("legs", []),
        })

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

        pnl_pct = (final_pnl / (cfg.capital or 100000)) * 100
        if final_pnl >= 0:
            _notify(db, "notify_tp_hit", intent.strategy, final_pnl, pnl_pct)
        else:
            _notify(db, "notify_sl_hit", intent.strategy, final_pnl, pnl_pct)

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
    ensure_auto_trader_schema(db.get_bind())
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
            entry_start_time=DEFAULT_ENTRY_START,
            entry_end_time=DEFAULT_ENTRY_END,
            use_ai_gate=False,
            ai_gate_min_confidence=0.65,
            trade_stocks=False,
            stock_symbols=[],
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)

    # Guard: JSON column may come back as string from DB (migration artifact)
    if isinstance(cfg.underlyings, str):
        import json as _json
        try:
            cfg.underlyings = _json.loads(cfg.underlyings)
        except Exception:
            cfg.underlyings = ["NIFTY"]

    needs_save = False
    if not getattr(cfg, "entry_start_time", None):
        cfg.entry_start_time = DEFAULT_ENTRY_START
        needs_save = True
    if not getattr(cfg, "entry_end_time", None):
        cfg.entry_end_time = DEFAULT_ENTRY_END
        needs_save = True
    if needs_save:
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
