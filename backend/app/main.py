# ⚡ LOAD ENV VARIABLES FIRST - BEFORE ANY IMPORTS
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend directory (before any other imports!)
backend_dir = Path(__file__).parent.parent
env_path = backend_dir / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# Now do all the imports
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.api.option_spread import router as option_spread_router
from app.api.routes import journal
from app.api.routes import intent
from app.api.routes import execute
from app.api.routes import account
from app.api.routes import strategies
from app.api.routes import execution_v2
from app.api.routes import settings
from app.api.routes import backtest
from app.api.routes import greeks
from app.api.routes import market
from app.api.routes import suggestions
from app.api.routes import stock_suggestions
from app.api.routes import screener
from app.api.routes import options
from app.api.routes import options_real
from app.api.routes import ws_positions
from app.api.routes.paper_mtm import router as paper_mtm_router
from app.api.routes.exit import router as exit_router
from app.api.routes.auto_exit import router as auto_exit_router
from app.api.system_control import router as system_router
from app.api.routes import notifications
from app.api.routes import websocket_routes
from app.api.routes import health
from app.api.routes.finance import router as finance_router
from app.api.routes import market_dashboard
from app.api.routes import swing_scanner
from app.api.routes import sentiment
from app.api.routes import config_routes
from app.api.routes import news
from app.api.routes import twitter
from app.api.routes import economic_calendar
from app.api.routes import market_depth
from app.api.routes import alerts
from app.api.routes import stock_news
from app.api.routes import timeframe_suggestions
from app.api.routes import peer_comparison
from app.api.routes import safety
from app.api.routes import ml
from app.api.routes import candles
from app.api.routes import zerodha_broker
from app.api.routes import indmoney_broker
from app.api.routes import position_suggestions
from app.api.routes import auto_trader as auto_trader_routes
from app.api.routes import auth
from app.api.routes import trade_costs
from app.api.routes import watchlists
from app.api.routes import condition_scanner
from app.api.routes import reconcile
from app.api.routes import analytics
from app.api.routes import marketplace
from app.api.routes import ai_chat
from app.api.routes import alexa
from app.api.routes import simple_ai
from app.core.auth import require_authenticated_user

from app.core.market.scheduler import (
    start_candle_scheduler,
    start_daily_candles_scheduler,
    start_intraday_candles_scheduler,
    start_vix_scheduler,
    start_auto_exit_scheduler,
    start_expiry_exit_scheduler,
    start_twitter_sentiment_scheduler,
    start_neon_sync_scheduler,
    start_zerodha_auto_login_scheduler,
    start_strategy_discovery_scheduler,
    start_strategy_decay_scheduler,
    initialize_vix_data,
    stop_scheduler,
)
from app.core.logging_config import setup_logging, set_request_id, get_request_id
from app.services.health_monitor import performance_tracker
import logging
import time
import asyncio

# Setup enhanced logging
import os
log_level = os.getenv("LOG_LEVEL", "INFO")
json_logs = os.getenv("JSON_LOGS", "false").lower() == "true"
setup_logging(log_level=log_level, json_logs=json_logs)

logger = logging.getLogger(__name__)

# Safe env check — log presence only, never log key length or content
newsdata_key = os.getenv("NEWSDATA_API_KEY", "")
zerodha_key = os.getenv("ZERODHA_API_KEY", "")
logger.info(f"📝 Environment loaded: NEWSDATA_API_KEY={'✅' if newsdata_key else '❌ MISSING'}, ZERODHA_API_KEY={'✅' if zerodha_key else '❌ MISSING'}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 🔹 Startup
    logger.info("🚀 App starting")
    
    # Initialize database tables (create if missing)
    try:
        from app.db.session import engine
        from app.db.models import Base
        from app.db.models_notification import Notification
        from app.db.models_risk import RiskLimitConfig  # noqa: F401 ensures table registration
        from app.db.models_auto_trader import AutoTraderConfig, AutoTraderLog, ensure_auto_trader_schema  # noqa: F401
        from app.db.models_signal_outcome import SignalOutcome  # noqa: F401
        from app.db.models_scanner_signal import ScannerSignalHistory  # noqa: F401
        from app.db.models_zerodha import ZerodhaSession  # noqa: F401
        Base.metadata.create_all(bind=engine)
        ensure_auto_trader_schema(engine)
        logger.info("✅ Database tables initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
    
    # Initialize VIX data and start schedulers
    try:
        # Get startup delay config from environment (prevents startup blocking)
        daily_backfill_delay = int(os.getenv("DAILY_BACKFILL_DELAY_MINUTES", "5"))
        vix_backfill_delay = int(os.getenv("VIX_BACKFILL_DELAY_MINUTES", "2"))
        
        initialize_vix_data()
        start_candle_scheduler()
        start_daily_candles_scheduler(delay_minutes=daily_backfill_delay)
        start_vix_scheduler(delay_minutes=vix_backfill_delay)
        start_auto_exit_scheduler()  # Monitor TP/SL/Trailing stops
        start_expiry_exit_scheduler()  # Auto-exit options near expiry
        start_intraday_candles_scheduler(delay_minutes=3)  # 5m + 1h candles
        start_twitter_sentiment_scheduler()  # Twitter market sentiment
        start_neon_sync_scheduler()            # Hourly delta backup to Neon
        start_zerodha_auto_login_scheduler()    # Daily auto-login at 8 AM IST
        start_strategy_discovery_scheduler()    # Daily strategy discovery at 4:15 PM IST
        start_strategy_decay_scheduler()         # Daily decay check at 4:30 PM IST
        logger.info("✅ Schedulers started")
    except Exception as e:
        logger.warning(f"⚠️ Schedulers failed to start: {e}")

    # Fire Zerodha auto-login immediately on startup
    try:
        import threading
        from app.core.market.scheduler import _zerodha_auto_login_job
        threading.Thread(target=_zerodha_auto_login_job, name="zerodha-startup-login", daemon=True).start()
        logger.info("🔐 Zerodha auto-login triggered on startup")
    except Exception as e:
        logger.warning(f"⚠️ Zerodha startup login failed: {e}")

    # Resume auto-trader scheduler if it was RUNNING before restart
    try:
        from app.db.session import SessionLocal as _SL
        from app.db.models_auto_trader import AutoTraderConfig as _ATC
        from app.core.auto_trader import _ensure_scheduler_job, reset_daily_counters
        _db = _SL()
        _cfg = _db.query(_ATC).first()
        if _cfg and _cfg.enabled and _cfg.status == "RUNNING":
            _ensure_scheduler_job(_cfg.scan_interval_sec or 30)
            # Reset daily counters on fresh server start
            reset_daily_counters(_db)
            logger.info("✅ Auto-trader scheduler resumed (was RUNNING before restart)")
        _db.close()
    except Exception as e:
        logger.warning(f"⚠️ Auto-trader resume failed: {e}")

    # Resume condition-scanner scheduler if any strategies have auto_scan_enabled
    try:
        from app.core.condition_scanner_scheduler import resume_scanner_on_startup
        resume_scanner_on_startup()
    except Exception as e:
        logger.warning(f"⚠️ Condition scanner resume failed: {e}")
    
    # Start WebSocket background tasks
    # FIX: Initialize to None before try block — prevents NameError on shutdown
    # if task creation fails mid-way.
    mtm_task = None
    health_task = None
    db = None
    try:
        from app.services.websocket import periodic_mtm_updates, periodic_system_health
        from app.db.session import SessionLocal
        
        db = SessionLocal()
        
        # Create background tasks
        mtm_task = asyncio.create_task(periodic_mtm_updates(db))
        health_task = asyncio.create_task(periodic_system_health(db))
        
        logger.info("✅ WebSocket background tasks started")
    except Exception as e:
        logger.warning(f"⚠️ WebSocket tasks failed to start: {e}")

    yield  # 👈 App runs here

    # 🔹 Shutdown
    logger.info("🛑 App shutting down")
    stop_scheduler()
    
    # Cancel background tasks (guard against None if startup failed)
    if mtm_task:
        mtm_task.cancel()
    if health_task:
        health_task.cancel()
    if mtm_task or health_task:
        logger.info("✅ Background tasks cancelled")

    # FIX: Always close the DB session opened at startup
    if db:
        db.close()
        logger.info("✅ Startup DB session closed")


app = FastAPI(
    title="AI ML Trading Backend",
    version="2.0.0",
    description="Backend engine for option spread strategies with real-time monitoring",
     lifespan=lifespan,
)

# 🔐 CORS Middleware - Allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",      # Frontend dev server
        "http://localhost:5173",      # Vite dev server
        "http://localhost:5174",      # Alternative Vite port
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info("✅ CORS middleware enabled for frontend requests")


# 🔍 Request ID & Performance Tracking Middleware
@app.middleware("http")
async def add_request_id_and_track_performance(request: Request, call_next):
    """Add request ID to context and track API performance"""
    # Set request ID
    request_id = set_request_id()
    request.state.request_id = request_id
    
    # Track performance
    start_time = time.time()
    
    try:
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Track in performance monitor
        performance_tracker.record_request(request.url.path, duration_ms)
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"Request failed: {request.url.path} ({duration_ms:.2f}ms)", exc_info=True)
        raise


# 🔗 Register routers
app.include_router(
    option_spread_router,
    prefix="/strategy",
    tags=["Option Spreads"],
    dependencies=[Depends(require_authenticated_user)],
)

@app.get("/")
def health_check():
    return {"status": "ok", "service": "trading-backend"}

app.include_router(journal.router)
app.include_router(auth.router)
app.include_router(intent.router, dependencies=[Depends(require_authenticated_user)])
app.include_router(execute.router, dependencies=[Depends(require_authenticated_user)])
app.include_router(account.router, dependencies=[Depends(require_authenticated_user)])
app.include_router(strategies.router, dependencies=[Depends(require_authenticated_user)])
app.include_router(execution_v2.router, dependencies=[Depends(require_authenticated_user)])
app.include_router(settings.router, dependencies=[Depends(require_authenticated_user)])
app.include_router(backtest.router)
app.include_router(greeks.router)
app.include_router(market.router)
app.include_router(screener.router)
app.include_router(options.router)
app.include_router(options_real.router)
app.include_router(suggestions.router)
app.include_router(stock_suggestions.router)
app.include_router(ws_positions.router)
app.include_router(alerts.router)
app.include_router(paper_mtm_router, dependencies=[Depends(require_authenticated_user)])
app.include_router(exit_router, dependencies=[Depends(require_authenticated_user)])
app.include_router(auto_exit_router, dependencies=[Depends(require_authenticated_user)])
app.include_router(system_router, dependencies=[Depends(require_authenticated_user)])
app.include_router(ml.router)
#  Phase 5 Features
app.include_router(notifications.router)
app.include_router(websocket_routes.router)
app.include_router(health.router)
app.include_router(finance_router)
app.include_router(market_dashboard.router)
app.include_router(swing_scanner.router)
app.include_router(sentiment.router)
app.include_router(news.router)
app.include_router(twitter.router)
app.include_router(economic_calendar.router)
app.include_router(market_depth.router)
app.include_router(config_routes.router)
app.include_router(stock_news.router)
app.include_router(timeframe_suggestions.router)
app.include_router(peer_comparison.router)
app.include_router(safety.router)
app.include_router(candles.router)
app.include_router(zerodha_broker.router, dependencies=[Depends(require_authenticated_user)])
app.include_router(indmoney_broker.router, dependencies=[Depends(require_authenticated_user)])
app.include_router(position_suggestions.router)
app.include_router(auto_trader_routes.router, dependencies=[Depends(require_authenticated_user)])
app.include_router(trade_costs.router)
app.include_router(watchlists.router)
app.include_router(condition_scanner.router)
app.include_router(reconcile.router, dependencies=[Depends(require_authenticated_user)])
app.include_router(analytics.router, dependencies=[Depends(require_authenticated_user)])
app.include_router(marketplace.router, dependencies=[Depends(require_authenticated_user)])
app.include_router(ai_chat.router)
app.include_router(alexa.router)
app.include_router(simple_ai.router)

logger.info(" All routers registered (including Phase 5 features)")