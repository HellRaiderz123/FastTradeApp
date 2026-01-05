import logging
from apscheduler.schedulers.background import BackgroundScheduler
from app.db.session import SessionLocal
from app.core.market.candles import fetch_15m_candles

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


def start_candle_scheduler():
    if scheduler.running:
        logger.warning("⚠️ Candle scheduler already running")
        return

    scheduler.add_job(
        func=_update,
        trigger="cron",
        minute="*/15",
        id="candle_15m_job",          # ✅ important
        replace_existing=True,        # ✅ important
        max_instances=1,              # ✅ prevents overlap
        coalesce=True,                # ✅ merges missed runs
    )

    scheduler.start()
    logger.info("🟢 Candle scheduler started")
    _update()  # Initial run

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("🛑 Candle scheduler stopped")
