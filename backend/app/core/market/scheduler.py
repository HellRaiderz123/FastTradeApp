import logging
from apscheduler.schedulers.background import BackgroundScheduler
from app.db.session import SessionLocal
from app.core.market.candles import fetch_15m_candles
from app.core.market.zerodha_historic_fetcher import (
    fetch_and_store_daily_vix,
    initialize_vix_historic_data,
)

logger = logging.getLogger(__name__)

# ✅ ONE global scheduler
scheduler = BackgroundScheduler(timezone="Asia/Kolkata")


def _update():
    logger.info("⏱️ Running 15m candle update")

    db = SessionLocal()
    try:
        fetch_15m_candles(db, "NIFTY")
        logger.info("✅ 15m candles updated")
    except Exception:
        logger.exception("❌ Candle update failed")
    finally:
        db.close()


def _update_daily_vix():
    """Update daily VIX data and calculate IV Rank."""
    logger.info("⏱️ Running daily VIX update")
    
    db = SessionLocal()
    try:
        success = fetch_and_store_daily_vix(db)
        if success:
            logger.info("✅ Daily VIX updated and IV Rank calculated")
        else:
            logger.warning("⚠️ Daily VIX update partially failed")
    except Exception:
        logger.exception("❌ Daily VIX update failed")
    finally:
        db.close()


def start_candle_scheduler():
    if scheduler.running:
        logger.warning("⚠️ Candle scheduler already running")
        return

    scheduler.add_job(
        func=_update,
        trigger="cron",
        minute="*/5",
        id="candle_15m_job",          # ✅ important
        replace_existing=True,        # ✅ important
        max_instances=1,              # ✅ prevents overlap
        coalesce=True,                # ✅ merges missed runs
    )

    scheduler.start()
    logger.info("🟢 Candle scheduler started")
    _update()  # Initial run


def start_vix_scheduler():
    """Start daily VIX update scheduler (runs at market close)."""
    if not scheduler.running:
        logger.warning("⚠️ Cannot start VIX scheduler: main scheduler not running")
        return
    
    # Schedule daily VIX update at 3:45 PM IST (market close is 3:30 PM)
    scheduler.add_job(
        func=_update_daily_vix,
        trigger="cron",
        hour=15,
        minute=45,
        id="daily_vix_job",
        replace_existing=True,
        max_instances=1,
    )
    
    logger.info("🟢 VIX daily scheduler started (3:45 PM IST)")
    # Also run immediately on startup to ensure data is fresh
    _update_daily_vix()


def initialize_vix_data():
    """Initialize VIX historic data on startup."""
    logger.info("🔄 Initializing VIX historic data...")
    
    db = SessionLocal()
    try:
        success = initialize_vix_historic_data(db)
        if success:
            logger.info("✅ VIX historic data initialized")
            return True
        else:
            logger.warning("⚠️ Could not initialize VIX data from Zerodha")
            logger.info("   → Try running fetch_vix_historic_from_zerodha manually")
            return False
    except Exception as e:
        logger.exception(f"❌ VIX initialization failed: {e}")
        return False
    finally:
        db.close()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("🛑 Scheduler stopped")

