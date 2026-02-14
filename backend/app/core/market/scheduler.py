import logging
import os
from apscheduler.schedulers.background import BackgroundScheduler
from app.db.session import SessionLocal
from app.core.market.candles import fetch_15m_candles, fetch_daily_candles
from app.core.market.zerodha_historic_fetcher import (
    fetch_and_store_daily_vix,
    initialize_vix_historic_data,
)
from app.core.exit.auto_exit import run_auto_exit

logger = logging.getLogger(__name__)

# ✅ ONE global scheduler
scheduler = BackgroundScheduler(timezone="Asia/Kolkata")


def _update():
    logger.info("⏱️ Running 15m candle update")

    db = SessionLocal()
    try:
        fetch_15m_candles(db, "NIFTY")
        fetch_15m_candles(db, "BANKNIFTY")
        fetch_15m_candles(db, "FINNIFTY")
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


def _get_daily_symbols() -> list[str]:
    raw = os.getenv("STOCK_DAILY_SYMBOLS", "").strip()
    if raw:
        return [s.strip().upper() for s in raw.split(",") if s.strip()]

    return [
        "RELIANCE",
        "TCS",
        "INFY",
        "HDFCBANK",
        "ICICIBANK",
        "SBIN",
        "BHARTIARTL",
        "KOTAKBANK",
        "ITC",
        "HINDUNILVR",
    ]


def _update_daily_candles():
    """Update daily candles for swing trading."""
    days = int(os.getenv("DAILY_CANDLES_DAYS", "900"))
    symbols = _get_daily_symbols()
    logger.info("⏱️ Running daily candle update | symbols=%d | days=%d", len(symbols), days)

    db = SessionLocal()
    try:
        for symbol in symbols:
            fetch_daily_candles(db, symbol, days=days)
        logger.info("✅ Daily candles updated")
    except Exception:
        logger.exception("❌ Daily candles update failed")
    finally:
        db.close()


def _auto_exit_check():
    """Check TP/SL/Trailing stops and auto-exit positions."""
    db = SessionLocal()
    try:
        exited = run_auto_exit(db)
        if exited:
            logger.info(f"🚪 Auto-exited {len(exited)} position(s): {exited}")
    except Exception:
        logger.exception("❌ Auto-exit check failed")
    finally:
        db.close()


def _train_ml_model():
    """Train stock ML model on accumulated daily data (weekly job)."""
    logger.info("⏱️ Running ML model training")
    
    db = SessionLocal()
    try:
        from app.core.ml.config import StockMLConfig
        from app.core.ml.stock_model import train_stock_model
        
        config = StockMLConfig()
        if not config.enabled:
            logger.info("⏩ ML training skipped (STOCK_ML_ENABLED=false)")
            return
        
        # Get symbols from environment (same as daily candles)
        symbols = _get_daily_symbols()
        if not symbols:
            logger.warning("⚠️ No symbols configured for ML training")
            return
        
        # Train on daily timeframe (better for swing trading ML)
        metadata = train_stock_model(db, symbols, config)
        
        accuracy = metadata.get('accuracy', 'N/A')
        n_samples = metadata.get('n_samples', 0)
        logger.info(f"✅ ML model trained: {accuracy} accuracy, {n_samples} samples")
    except ImportError:
        logger.warning("⚠️ ML modules not available, skipping training")
    except Exception:
        logger.exception("❌ ML model training failed")
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


def start_daily_candles_scheduler():
    """Start daily candle update scheduler (runs after market close)."""
    if not scheduler.running:
        logger.warning("⚠️ Cannot start daily candles scheduler: main scheduler not running")
        return

    scheduler.add_job(
        func=_update_daily_candles,
        trigger="cron",
        day_of_week="mon-fri",
        hour=15,
        minute=50,
        id="daily_candles_job",
        replace_existing=True,
        max_instances=1,
    )

    logger.info("🟢 Daily candles scheduler started (3:50 PM IST)")
    _update_daily_candles()


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


def start_auto_exit_scheduler():
    """Start TP/SL/Trailing stop monitoring (runs every 10 seconds during market hours 9:15 AM - 3:30 PM)."""
    if not scheduler.running:
        logger.warning("⚠️ Cannot start auto-exit scheduler: main scheduler not running")
        return
    
    # Run every 10 seconds, but only during market hours (9:15 AM - 3:30 PM IST)
    scheduler.add_job(
        func=_auto_exit_check,
        trigger="cron",
        day_of_week="mon-fri",
        hour="9-15",  # 9 AM to 3 PM
        second="*/10",  # Every 10 seconds
        id="auto_exit_job",
        replace_existing=True,
        max_instances=1,
    )
    
    logger.info("🟢 Auto-exit scheduler started (every 10 seconds, market hours only)")


def start_ml_training_scheduler():
    """Start weekly ML model training (runs every Sunday at 4 AM IST)."""
    if not scheduler.running:
        logger.warning("⚠️ Cannot start ML training scheduler: main scheduler not running")
        return
    
    scheduler.add_job(
        func=_train_ml_model,
        trigger="cron",
        day_of_week="sun",  # Sunday
        hour=4,  # 4 AM IST
        minute=0,
        id="ml_training_job",
        replace_existing=True,
        max_instances=1,
    )
    
    logger.info("🟢 ML training scheduler started (Sundays at 4 AM IST)")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("🛑 Scheduler stopped")

