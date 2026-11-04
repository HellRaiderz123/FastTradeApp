"""
Scheduler Initialization Module

Extracted from main.py to reduce complexity.
Handles all APScheduler job registration and lifecycle management.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def initialize_schedulers(engine: "Engine") -> None:
    """
    Initialize all background schedulers.

    Auto-trader, auto-exit, expiry-exit, and holdings-auto-exit always start
    regardless of SCHEDULERS_ENABLED so trading jobs are never silently skipped.
    """
    from app.core.market.scheduler import (
        start_candle_scheduler,
        start_daily_candles_scheduler,
        start_intraday_candles_scheduler,
        start_vix_scheduler,
        start_auto_exit_scheduler,
        start_expiry_exit_scheduler,
        start_twitter_sentiment_scheduler,
        start_nifty100_reconciliation_scheduler,
        start_holdings_reconciliation_scheduler,
        start_neon_sync_scheduler,
        start_zerodha_auto_login_scheduler,
        start_strategy_discovery_scheduler,
        start_strategy_decay_scheduler,
        start_watchlist_analysis_scheduler,
        start_holdings_auto_exit_scheduler,
        start_nse_filing_alerts_scheduler,
        start_nse_snapshot_scheduler,
        initialize_vix_data,
        scheduler as _apscheduler,
    )

    # ── Always-on trading jobs (ignore SCHEDULERS_ENABLED) ────────────────
    # These must run at all times: auto-trader scan, TP/SL exit monitor,
    # expiry-day force-exit, and holdings auto-exit.
    _start_always_on_scheduler(
        _apscheduler,
        start_auto_exit_scheduler,
        start_expiry_exit_scheduler,
        start_holdings_auto_exit_scheduler,
        engine,
    )

    schedulers_enabled = os.getenv("SCHEDULERS_ENABLED", "true").lower() == "true"

    if not schedulers_enabled:
        logger.info("⏭️ Optional schedulers DISABLED (SCHEDULERS_ENABLED=false) — trading jobs still active")
        return

    broker_ready = _broker_token_available()
    if not broker_ready:
        logger.warning(
            "⚠️  No broker token found — broker-dependent schedulers will NOT start. "
            "Set token via login flow or Settings."
        )

    daily_backfill_delay = int(os.getenv("DAILY_BACKFILL_DELAY_MINUTES", "5"))
    vix_backfill_delay = int(os.getenv("VIX_BACKFILL_DELAY_MINUTES", "2"))

    # Scheduler is already running (started by _start_always_on_scheduler above)
    # No need to call _apscheduler.start() again

    # Always start broker-independent schedulers
    start_strategy_discovery_scheduler()
    start_strategy_decay_scheduler()
    start_watchlist_analysis_scheduler()
    start_nse_filing_alerts_scheduler()
    start_nse_snapshot_scheduler()
    logger.info("✅ Broker-independent schedulers started")

    # Only start broker-dependent schedulers if a token exists
    if broker_ready:
        threading.Thread(target=initialize_vix_data, name="vix-init", daemon=True).start()
        start_candle_scheduler()
        start_daily_candles_scheduler(delay_minutes=daily_backfill_delay)
        start_vix_scheduler(delay_minutes=vix_backfill_delay)
        start_intraday_candles_scheduler(delay_minutes=3)
        start_twitter_sentiment_scheduler()
        start_nifty100_reconciliation_scheduler()
        start_holdings_reconciliation_scheduler()
        start_neon_sync_scheduler()
        start_zerodha_auto_login_scheduler()
        logger.info("✅ Broker-dependent schedulers started")
    else:
        logger.warning("⏭️  Broker-dependent schedulers SKIPPED (no valid token)")

    # Resume condition scanner
    _resume_condition_scanner()

    # Schedule AI job cleanup
    _schedule_ai_cleanup()

    # Schedule AI outcome evaluation
    _schedule_ai_outcome_evaluation()

    # Schedule INDstocks instruments sync
    _schedule_instruments_sync()


def _start_always_on_scheduler(apscheduler, start_auto_exit_fn, start_expiry_exit_fn, start_holdings_exit_fn, engine):
    """
    Start the APScheduler instance and register the 4 trading-critical jobs
    that must always run regardless of SCHEDULERS_ENABLED:
      - auto_exit_job       : TP/SL/trailing-stop monitor (every 10s, market hours)
      - expiry_exit_job     : force-exit on expiry day (every 1min, market hours)
      - holdings_auto_exit  : scanner/AI holding TP/SL (every 1min, market hours)
      - auto_trader_scan    : auto-trader engine (interval, resumed from DB state)
    """
    # Start scheduler FIRST so all subsequent add_job calls succeed
    if not apscheduler.running:
        apscheduler.start()
        logger.info("✅ APScheduler started (always-on trading jobs)")

    # These functions guard on `if not scheduler.running` internally — scheduler is running now
    start_auto_exit_fn()
    start_expiry_exit_fn()
    start_holdings_exit_fn()
    logger.info("✅ Always-on trading jobs registered: auto-exit, expiry-exit, holdings-exit")

    # Resume auto-trader immediately (before optional schedulers block)
    _resume_auto_trader(engine)


def _broker_token_available() -> bool:
    """Check if a valid broker token exists."""
    try:
        from app.core.broker.registry import get_active_broker
        broker = get_active_broker()
        
        if broker == "ZERODHA":
            from app.db.session import SessionLocal
            from app.core.broker.zerodha.oauth import get_active_session
            db = SessionLocal()
            try:
                if get_active_session(db):
                    return True
            finally:
                db.close()
            return bool(os.getenv("ZERODHA_ACCESS_TOKEN", ""))
        
        elif broker == "INDMONEY":
            from app.db.session import SessionLocal
            from app.db.models_indmoney import INDMoneySession
            db = SessionLocal()
            try:
                s = db.query(INDMoneySession).filter(INDMoneySession.is_active == 1).first()
                if s:
                    return True
            finally:
                db.close()
            return bool(os.getenv("INDMONEY_ACCESS_TOKEN", ""))
    except Exception as e:
        logger.warning("Broker token pre-check failed: %s", e)
    return False


def _resume_auto_trader(engine: "Engine") -> None:
    """Resume auto-trader scheduler if it was RUNNING before restart."""
    try:
        from app.db.session import SessionLocal
        from app.db.models_auto_trader import AutoTraderConfig
        from app.core.auto_trader import _ensure_scheduler_job, reset_daily_counters
        
        db = SessionLocal()
        cfg = db.query(AutoTraderConfig).first()
        if cfg and cfg.enabled and cfg.status == "RUNNING":
            _ensure_scheduler_job(cfg.scan_interval_sec or 30)
            reset_daily_counters(db)
            logger.info("✅ Auto-trader scheduler resumed (was RUNNING before restart)")
        db.close()
    except Exception as e:
        logger.warning("⚠️ Auto-trader resume failed: %s", e)


def _resume_condition_scanner() -> None:
    """Resume condition-scanner scheduler."""
    try:
        from app.core.condition_scanner_scheduler import resume_scanner_on_startup
        resume_scanner_on_startup()
    except Exception as e:
        logger.warning("⚠️ Condition scanner resume failed: %s", e)


def _schedule_ai_cleanup() -> None:
    """Schedule AI job cleanup every 30 minutes."""
    try:
        from apscheduler.triggers.interval import IntervalTrigger
        from app.core.market.scheduler import scheduler
        from app.services.trading_agents import cleanup_expired_jobs

        scheduler.add_job(
            cleanup_expired_jobs,
            trigger=IntervalTrigger(minutes=30),
            id="ai_job_cleanup",
            replace_existing=True,
        )
        logger.info("✅ AI job cleanup scheduled (every 30 min)")
    except Exception as e:
        logger.warning("⚠️ AI job cleanup scheduler failed: %s", e)


def _schedule_ai_outcome_evaluation() -> None:
    """Schedule daily AI outcome evaluation."""
    try:
        from app.core.market.scheduler import scheduler
        from app.services.trading_agents import evaluate_pending_outcomes

        def _run_outcome_evaluation():
            updated = evaluate_pending_outcomes(evaluation_days=3)
            if updated:
                logger.info("🤖 AI outcome evaluation: %d decisions evaluated", updated)

        scheduler.add_job(
            _run_outcome_evaluation,
            trigger="cron",
            day_of_week="mon-fri",
            hour=16,
            minute=45,
            timezone="Asia/Kolkata",
            id="ai_outcome_evaluator",
            replace_existing=True,
        )
        logger.info("✅ AI outcome evaluator scheduled (daily)")
    except Exception as e:
        logger.warning("⚠️ AI outcome evaluator scheduler failed: %s", e)


def _schedule_instruments_sync() -> None:
    """Schedule daily INDstocks instruments re-sync."""
    try:
        from apscheduler.triggers.cron import CronTrigger
        from app.core.market.scheduler import scheduler
        from app.core.broker.indstocks.instruments_sync import sync_instruments

        scheduler.add_job(
            lambda: sync_instruments(force=True),
            trigger=CronTrigger(hour=8, minute=0, timezone="Asia/Kolkata"),
            id="instruments_daily_sync",
            replace_existing=True,
        )
        logger.info("✅ INDstocks instruments daily re-sync scheduled (08:00 IST)")
    except Exception as e:
        logger.warning("⚠️ INDstocks instruments daily sync scheduler failed: %s", e)


def stop_all_schedulers() -> None:
    """Stop all schedulers gracefully."""
    try:
        from app.core.market.scheduler import stop_scheduler
        stop_scheduler()
        logger.info("✅ All schedulers stopped")
    except Exception as e:
        logger.warning("⚠️ Scheduler shutdown failed: %s", e)
