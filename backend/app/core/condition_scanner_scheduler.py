"""
condition_scanner_scheduler.py
------------------------------
Background scheduler for condition-scanner strategies.
Runs at configurable intervals (per-strategy timeframe),
scans symbols, and auto-executes trades when signals fire.

Uses the same APScheduler global singleton as auto_trader.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, time as dtime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.execution.mode import get_execution_mode, is_paper_mode, is_live_mode
from app.core.indicators.technical import TechnicalIndicators
from app.core.learning.scanner_signal_history import mark_signal_execution, record_scanner_signal
from app.config.market_config import get_symbols
from app.db.models_candles import CandleDaily
from app.db.session import SessionLocal
from app.services.zerodha import KiteConnectService

logger = logging.getLogger(__name__)

_scan_lock = threading.Lock()
_kite_service = KiteConnectService()

# Job ID prefix — each strategy gets its own job
_JOB_PREFIX = "cond_scanner_"

# ── Timeframe → interval seconds mapping ────────────────────────────────────

TIMEFRAME_INTERVALS = {
    "1 Min": 60,
    "5 Min": 300,
    "15 Min": 900,
    "1 Hour": 3600,
    "Day": 86400,     # once per day
}


def _get_interval_for_timeframe(timeframe: str) -> int:
    """Convert strategy timeframe to scan interval in seconds."""
    return TIMEFRAME_INTERVALS.get(timeframe, 3600)


def _is_market_hours() -> bool:
    """Check if current time is within Indian market hours (9:15 to 15:30)."""
    try:
        from app.core.utils.time import now_ist
        now = now_ist()
    except Exception:
        now = datetime.now()
    t = now.time()
    return dtime(9, 15) <= t <= dtime(15, 30)


# ── Core scan function (called by APScheduler) ─────────────────────────────

def condition_scanner_auto_scan():
    """
    Called by APScheduler. Opens its own DB session.
    Scans ALL active auto-scan strategies, and auto-executes signals.
    """
    if not _scan_lock.acquire(blocking=False):
        logger.debug("Condition scanner auto-scan skipped — previous scan still running")
        return

    db = SessionLocal()
    try:
        _run_all_strategies(db)
    except Exception as exc:
        logger.exception("Condition scanner auto-scan failed: %s", exc)
    finally:
        db.close()
        _scan_lock.release()


def _run_all_strategies(db: Session):
    """Iterate all strategies with auto_scan_enabled=True and run them."""
    from app.api.routes.condition_scanner import (
        _load_strategies, _save_strategies, _scan_symbol,
    )

    if not _is_market_hours():
        logger.debug("Condition scanner: outside market hours, skipping")
        return

    strategies = _load_strategies()
    auto_strategies = [s for s in strategies if s.get("auto_scan_enabled")]

    if not auto_strategies:
        return

    logger.info(f"🔍 Condition scanner auto-scan: {len(auto_strategies)} active strategies")

    for strategy in auto_strategies:
        try:
            _scan_and_execute_strategy(strategy, strategies, db)
        except Exception as exc:
            logger.error(f"Condition scanner: strategy '{strategy.get('name')}' failed: {exc}")

    # Save updated metadata
    _save_strategies(strategies)


def _scan_and_execute_strategy(strategy: dict, all_strategies: list, db: Session):
    """Scan one strategy and auto-execute any signals."""
    from app.api.routes.condition_scanner import _scan_symbol

    strategy_id = strategy.get("id")
    name = strategy.get("name", "unknown")
    conditions = strategy.get("entry_conditions", [])
    direction = strategy.get("direction", "BUY")
    timeframe = strategy.get("timeframe")
    exit_config = strategy.get("exit_config", {})
    universe = strategy.get("universe", "NIFTY50")
    instruments = strategy.get("instruments", [])

    if not conditions:
        return

    symbols = instruments if instruments else get_symbols(universe)

    # Get live quotes
    quotes_data = _kite_service.get_bulk_quotes(symbols) or {}

    signals = []
    for symbol in symbols:
        ltp = None
        volume = None
        quote = quotes_data.get(f"NSE:{symbol}")
        if quote:
            ltp = quote.get("last_price")
            volume = quote.get("volume")

        result = _scan_symbol(symbol, conditions, db, ltp=ltp, volume=volume)
        if result:
            signals.append(result)

    # Update scan metadata
    strategy["last_scan"] = datetime.now().isoformat()
    strategy["last_signal_count"] = len(signals)

    if not signals:
        logger.info(f"  📭 {name}: 0 signals from {len(symbols)} symbols")
        return

    logger.info(f"  📬 {name}: {len(signals)} signal(s) found! Auto-executing...")

    # Auto-execute each signal
    mode = get_execution_mode()
    auto_amount = strategy.get("auto_amount", 10000.0)

    for sig in signals:
        # Calculate quantity from amount and current price
        ltp = sig["ltp"]
        quantity = max(1, int(auto_amount // ltp)) if ltp and ltp > 0 else 1
        logger.info(f"    💰 Amount=₹{auto_amount:,.0f}, LTP=₹{ltp:.2f} → qty={quantity}")

        history = record_scanner_signal(
            db,
            strategy_id=strategy_id,
            strategy_name=name,
            symbol=sig["symbol"],
            direction=direction,
            timeframe=timeframe,
            universe=universe,
            signal_payload=sig,
            auto_execute=True,
            execution_mode=mode,
        )

        try:
            _auto_execute_signal(
                history_id=history.id if history else None,
                strategy_id=strategy_id,
                symbol=sig["symbol"],
                ltp=ltp,
                direction=direction,
                strategy_name=name,
                exit_config=exit_config,
                timeframe=timeframe,
                universe=universe,
                quantity=quantity,
                mode=mode,
                db=db,
            )
        except Exception as exec_err:
            logger.error(f"    ❌ Auto-execute {sig['symbol']} failed: {exec_err}")
            mark_signal_execution(
                db,
                history_id=history.id if history else None,
                strategy_id=strategy_id,
                strategy_name=name,
                symbol=sig["symbol"],
                direction=direction,
                status="FAILED",
                execution_payload={"error": str(exec_err), "auto_executed": True},
                quantity=quantity,
                execution_mode=mode,
            )


def _auto_execute_signal(
    history_id: Optional[int],
    strategy_id: Optional[int],
    symbol: str,
    ltp: float,
    direction: str,
    strategy_name: str,
    exit_config: dict,
    timeframe: Optional[str],
    universe: Optional[str],
    quantity: int,
    mode: str,
    db: Session,
):
    """Execute a single trade signal based on execution mode."""
    order = {
        "symbol": symbol,
        "direction": direction,
        "strategy": strategy_name,
        "ltp": ltp,
        "quantity": quantity,
        "exit_config": exit_config,
        "auto_executed": True,
        "timestamp": datetime.now().isoformat(),
    }

    if is_paper_mode(mode):
        order["status"] = "FILLED_PAPER"
        order["order_id"] = f"AUTO-PAPER-{datetime.now().strftime('%Y%m%d%H%M%S')}-{symbol}"
        order["fill_price"] = ltp
        logger.info(f"    📝 Auto paper trade: {direction} {symbol} @ ₹{ltp}")

    elif is_live_mode(mode):
        try:
            from app.core.broker.zerodha.client import get_kite_client
            kite = get_kite_client()
            transaction_type = kite.TRANSACTION_TYPE_BUY if direction == "BUY" else kite.TRANSACTION_TYPE_SELL
            order_id = kite.place_order(
                variety=kite.VARIETY_REGULAR,
                exchange=kite.EXCHANGE_NSE,
                tradingsymbol=symbol,
                transaction_type=transaction_type,
                quantity=quantity,
                product=kite.PRODUCT_CNC,
                order_type=kite.ORDER_TYPE_MARKET,
            )
            order["status"] = "PLACED_LIVE"
            order["order_id"] = str(order_id)
            order["fill_price"] = ltp
            logger.info(f"    🔴 AUTO LIVE order: {direction} {symbol} @ ₹{ltp}, id={order_id}")
        except Exception as e:
            order["status"] = "FAILED"
            order["error"] = str(e)
            logger.error(f"    ❌ Auto live order failed: {e}")
    else:
        order["status"] = "DRY_RUN"
        order["order_id"] = f"AUTO-DRY-{datetime.now().strftime('%Y%m%d%H%M%S')}-{symbol}"
        order["fill_price"] = ltp
        logger.info(f"    🟡 Auto dry-run: {direction} {symbol} @ ₹{ltp}")

    mark_signal_execution(
        db,
        history_id=history_id,
        strategy_id=strategy_id,
        strategy_name=strategy_name,
        symbol=symbol,
        direction=direction,
        status=order.get("status", "SIGNAL_GENERATED"),
        execution_payload={
            **order,
            "timeframe": timeframe,
            "universe": universe,
        },
        quantity=quantity,
        execution_mode=mode,
        order_id=order.get("order_id"),
    )

    # Log to DB
    try:
        from app.db.models_auto_trader import AutoTraderLog
        log = AutoTraderLog(
            strategy=strategy_name,
            action="AUTO_ENTRY",
            symbol=symbol,
            direction=direction,
            price=ltp,
            quantity=quantity,
            execution_mode=mode,
            details=json.dumps(order),
            timestamp=datetime.now(),
        )
        db.add(log)
        db.commit()
    except Exception as log_err:
        logger.warning(f"    Could not log auto-execution: {log_err}")
        try:
            db.rollback()
        except Exception:
            pass


# ── Scheduler management ────────────────────────────────────────────────────

def _get_job_id() -> str:
    return f"{_JOB_PREFIX}auto"


def ensure_scanner_scheduler(interval_sec: int = 300):
    """Add or reschedule the condition scanner job on the global scheduler."""
    from app.core.market.scheduler import scheduler

    job_id = _get_job_id()
    if scheduler.get_job(job_id):
        scheduler.reschedule_job(job_id, trigger="interval", seconds=interval_sec)
    else:
        scheduler.add_job(
            condition_scanner_auto_scan,
            "interval",
            seconds=interval_sec,
            id=job_id,
            replace_existing=True,
            max_instances=1,
        )
    logger.info(f"📡 Condition scanner scheduler active (every {interval_sec}s)")


def remove_scanner_scheduler():
    """Remove the condition scanner job from the scheduler."""
    from app.core.market.scheduler import scheduler

    job_id = _get_job_id()
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info("📡 Condition scanner scheduler removed")


def get_scheduler_status() -> Dict[str, Any]:
    """Return current scheduler job status."""
    from app.core.market.scheduler import scheduler
    from app.api.routes.condition_scanner import _load_strategies

    job_id = _get_job_id()
    job = scheduler.get_job(job_id)

    strategies = _load_strategies()
    active_strategies = [s for s in strategies if s.get("auto_scan_enabled")]

    return {
        "scheduler_running": job is not None,
        "job_id": job_id,
        "next_run": str(job.next_run_time) if job else None,
        "active_strategies": len(active_strategies),
        "strategies": [
            {
                "id": s["id"],
                "name": s["name"],
                "timeframe": s.get("timeframe", ""),
                "last_scan": s.get("last_scan"),
                "last_signal_count": s.get("last_signal_count", 0),
                "auto_amount": s.get("auto_amount", 10000.0),
            }
            for s in active_strategies
        ],
    }


def resume_scanner_on_startup():
    """Called at server startup — resumes scheduler if any strategies are auto-enabled."""
    from app.api.routes.condition_scanner import _load_strategies

    try:
        strategies = _load_strategies()
        active = [s for s in strategies if s.get("auto_scan_enabled")]
        if active:
            # Use the shortest interval among active strategies
            intervals = [
                _get_interval_for_timeframe(s.get("timeframe", "1 Hour"))
                for s in active
            ]
            min_interval = min(intervals) if intervals else 300
            # Use at least 60 seconds to not overload
            min_interval = max(min_interval, 60)
            ensure_scanner_scheduler(min_interval)
            logger.info(f"✅ Condition scanner resumed: {len(active)} strategies, interval={min_interval}s")
        else:
            logger.info("📡 No auto-scan strategies active, scheduler not started")
    except Exception as e:
        logger.warning(f"⚠️ Condition scanner resume failed: {e}")
