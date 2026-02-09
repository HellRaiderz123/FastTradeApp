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
from fastapi import FastAPI, Request
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
from app.api.routes import economic_calendar
from app.api.routes import market_depth
from app.api.routes import alerts
from app.api.routes import stock_news
from app.api.routes import timeframe_suggestions
from app.api.routes import peer_comparison

from app.core.market.scheduler import (
    start_candle_scheduler,
    start_daily_candles_scheduler,
    start_vix_scheduler,
    start_auto_exit_scheduler,
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

# Debug: Show loaded environment variables
newsdata_key = os.getenv("NEWSDATA_API_KEY", "")
zerodha_key = os.getenv("ZERODHA_API_KEY", "")
logger.info(f"📝 Environment loaded: NEWSDATA_API_KEY={bool(newsdata_key)} (len={len(newsdata_key) if newsdata_key else 0}), ZERODHA_API_KEY={bool(zerodha_key)}")

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
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
    
    # Initialize VIX data and start schedulers
    try:
        initialize_vix_data()
        start_candle_scheduler()
        start_daily_candles_scheduler()
        start_vix_scheduler()
        start_auto_exit_scheduler()  # Monitor TP/SL/Trailing stops
        logger.info("✅ Schedulers started for live data updates + TP/SL monitoring")
    except Exception as e:
        logger.warning(f"⚠️ Schedulers failed to start: {e}")
    
    # Start WebSocket background tasks
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
    
    # Cancel background tasks
    try:
        mtm_task.cancel()
        health_task.cancel()
        logger.info("✅ Background tasks cancelled")
    except:
        pass


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
)

@app.get("/")
def health_check():
    return {"status": "ok", "service": "trading-backend"}

app.include_router(journal.router)
app.include_router(intent.router)
app.include_router(execute.router)
app.include_router(account.router)
app.include_router(strategies.router)
app.include_router(execution_v2.router)
app.include_router(settings.router)
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
app.include_router(paper_mtm_router)
app.include_router(exit_router)
app.include_router(auto_exit_router)
app.include_router(system_router)
#  Phase 5 Features
app.include_router(notifications.router)
app.include_router(websocket_routes.router)
app.include_router(health.router)
app.include_router(finance_router)
app.include_router(market_dashboard.router)
app.include_router(swing_scanner.router)
app.include_router(sentiment.router)
app.include_router(news.router)
app.include_router(economic_calendar.router)
app.include_router(market_depth.router)
app.include_router(config_routes.router)
app.include_router(stock_news.router)
app.include_router(timeframe_suggestions.router)
app.include_router(peer_comparison.router)

logger.info(" All routers registered (including Phase 5 features)")
