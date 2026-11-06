# ⚡ LOAD ENV VARIABLES FIRST - BEFORE ANY IMPORTS
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env — check multiple locations so it works both locally and in Docker
# Docker: env_file in docker-compose injects vars directly, load_dotenv is a no-op
# Local: loads from backend/.env
for _env_candidate in [
    Path(__file__).parent.parent / ".env",   # backend/.env  (local dev)
    Path("/app/.env"),                        # Docker WORKDIR /app/.env
    Path(".env"),                             # cwd fallback
]:
    if _env_candidate.exists():
        load_dotenv(dotenv_path=_env_candidate, override=False)  # don't override real env vars
        break

# Now do all the imports
import asyncio
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.logging_config import setup_logging
from app.core.middleware import setup_all_middleware
from app.core.router_registry import register_all_routers
from app.core.scheduler_init import initialize_schedulers, stop_all_schedulers

# Setup enhanced logging
log_level = os.getenv("LOG_LEVEL", "INFO")
json_logs = os.getenv("JSON_LOGS", "false").lower() == "true"
setup_logging(log_level=log_level, json_logs=json_logs)

logger = logging.getLogger(__name__)

# Safe env check — log presence only, never log key length or content
newsdata_key = os.getenv("NEWSDATA_API_KEY", "")
zerodha_key = os.getenv("ZERODHA_API_KEY", "")
logger.info(
    "📝 Environment loaded: NEWSDATA_API_KEY=%s, ZERODHA_API_KEY=%s",
    "✅" if newsdata_key else "❌ MISSING",
    "✅" if zerodha_key else "❌ MISSING",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager — handles startup and shutdown."""
    # 🔹 Startup
    logger.info("🚀 App starting")

    # Restore DB from R2 before anything else
    _restore_db_backup()

    # Initialize database tables
    engine = _initialize_database()

    # Sync INDstocks instruments in background
    _start_instruments_sync()

    # Initialize schedulers
    try:
        initialize_schedulers(engine)
    except Exception as e:
        logger.warning("⚠️ Schedulers failed to start: %s", e)

    # Wire event loop into trading_agents
    _wire_trading_agents_loop()

    # Start WebSocket background tasks
    mtm_task, health_task = await _start_websocket_tasks()

    yield  # 👈 App runs here

    # 🔹 Shutdown
    logger.info("🛑 App shutting down")
    stop_all_schedulers()

    # Backup DB to R2 before process exits
    _backup_db()

    # Cancel background tasks
    if mtm_task:
        mtm_task.cancel()
    if health_task:
        health_task.cancel()
    if mtm_task or health_task:
        logger.info("✅ Background tasks cancelled")


def _restore_db_backup() -> None:
    """Restore DB from R2 backup if configured."""
    try:
        from app.db.r2_backup import restore_from_r2, start_periodic_backup

        _b2_bucket = os.getenv("BACKUP_BUCKET_NAME", "")
        _b2_key_id = os.getenv("BACKUP_KEY_ID", "")
        _b2_app_key = os.getenv("BACKUP_APP_KEY", "")
        _b2_endpoint = os.getenv("BACKUP_ENDPOINT_URL", "")
        _b2_interval = os.getenv("BACKUP_INTERVAL_MINUTES", "60")

        logger.info(
            "🗄️  B2 backup config: BUCKET=%s | ENDPOINT=%s | KEY_ID=%s | APP_KEY=%s | INTERVAL=%s min",
            _b2_bucket or "❌ NOT SET",
            _b2_endpoint or "❌ NOT SET",
            ("✅ set (" + _b2_key_id[:6] + "...)") if _b2_key_id else "❌ NOT SET",
            "✅ set" if _b2_app_key else "❌ NOT SET",
            _b2_interval,
        )
        restore_from_r2()
        start_periodic_backup()
    except Exception as e:
        logger.warning("R2 restore/backup init failed: %s", e)


def _initialize_database():
    """Initialize database tables and run migrations.

    Each model import is wrapped individually so a missing/broken module
    never prevents the engine from being returned and schedulers from starting.
    """
    from app.db.session import engine
    from app.db.models import Base

    # Import each model separately — a bad import logs a warning but doesn't abort
    _optional_models = [
        "app.db.models_notification",
        "app.db.models_alexa",
        "app.db.models_risk",
        "app.db.models_auto_trader",
        "app.db.models_signal_outcome",
        "app.db.models_scanner_signal",
        "app.db.models_zerodha",
        "app.db.models_indmoney",
        "app.db.models_ai_decisions",
        "app.db.models_stock_holding",
        "app.db.models_instruments",
        "app.db.models_fundamentals",
        "app.db.models_nse",
        "app.db.models_fii_dii",
        "app.db.models_latency",
    ]
    for _mod in _optional_models:
        try:
            __import__(_mod)
        except Exception as _e:
            logger.warning("DB model import skipped (%s): %s", _mod, _e)

    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.error("❌ create_all failed: %s", e)

    # Schema helpers — each wrapped so one failure doesn't block the next
    try:
        from app.db.models_auto_trader import ensure_auto_trader_schema
        ensure_auto_trader_schema(engine)
    except Exception as e:
        logger.warning("ensure_auto_trader_schema skipped: %s", e)

    try:
        from app.db.models_ai_decisions import ensure_ai_decisions_schema
        ensure_ai_decisions_schema(engine)
    except Exception as e:
        logger.warning("ensure_ai_decisions_schema skipped: %s", e)

    # Column migrations
    try:
        from app.db.init_db import _MIGRATIONS_COMMON
        from sqlalchemy import text
        for stmt in _MIGRATIONS_COMMON:
            try:
                with engine.begin() as conn:
                    conn.execute(text(stmt))
            except Exception as e:
                logger.warning("Migration skipped (already applied or N/A): %s", e)
    except Exception as e:
        logger.warning("Migrations skipped: %s", e)

    logger.info("✅ Database tables initialized")
    return engine  # always return engine — never None


def _start_instruments_sync() -> None:
    """Start INDstocks instruments sync in background."""
    try:
        from app.core.broker.indstocks.instruments_sync import sync_instruments

        # force=True overwrites any stale scrip codes (e.g. old NSE_ index codes)
        threading.Thread(
            target=sync_instruments,
            kwargs={"force": True},
            name="instruments-sync",
            daemon=True
        ).start()
        logger.info("🔄 INDstocks instruments sync started in background")
    except Exception as e:
        logger.warning("⚠️ INDstocks instruments sync failed to start: %s", e)


def _wire_trading_agents_loop() -> None:
    """Wire event loop into trading_agents for WebSocket broadcasts."""
    try:
        from app.services.trading_agents import set_event_loop

        set_event_loop(asyncio.get_event_loop())
        logger.info("✅ TradingAgents event loop wired")
    except Exception as e:
        logger.warning("⚠️ TradingAgents event loop wiring failed: %s", e)


async def _start_websocket_tasks():
    """Start WebSocket background tasks."""
    mtm_task = None
    health_task = None
    try:
        from app.services.websocket import periodic_mtm_updates, periodic_system_health

        mtm_task = asyncio.create_task(periodic_mtm_updates())
        health_task = asyncio.create_task(periodic_system_health())
        logger.info("✅ WebSocket background tasks started")
    except Exception as e:
        logger.warning("⚠️ WebSocket tasks failed to start: %s", e)
    return mtm_task, health_task


def _backup_db() -> None:
    """Backup DB to R2 before shutdown."""
    try:
        from app.db.r2_backup import backup_to_r2

        backup_to_r2()
    except Exception as e:
        logger.warning("R2 backup on shutdown failed: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# Create FastAPI Application
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI ML Trading Backend",
    version="2.0.0",
    description="Backend engine for option spread strategies with real-time monitoring",
    lifespan=lifespan,
)

# Setup middleware
setup_all_middleware(app)

# Register all routers
register_all_routers(app)

# Register metrics router
from app.api.routes.metrics import router as metrics_router
app.include_router(metrics_router)

# Register latency router
from app.api.routes.latency import router as latency_router
app.include_router(latency_router)

# Register broker latency middleware
from app.core.latency_middleware import BrokerLatencyMiddleware
app.add_middleware(BrokerLatencyMiddleware)


@app.get("/")
def health_check():
    """Root health check endpoint."""
    return {"status": "ok", "service": "trading-backend"}


logger.info("✅ FastAPI application configured")
