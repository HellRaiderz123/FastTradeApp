from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.option_spread import router as option_spread_router
from app.api.routes import journal
from app.api.routes import intent
from app.api.routes import execute
from app.api.routes import account
from app.api.routes import strategies
from app.api.routes import execution_v2
from app.api.routes import settings
from app.api.routes.paper_mtm import router as paper_mtm_router
from app.api.routes.exit import router as exit_router
from app.api.routes.auto_exit import router as auto_exit_router
from app.api.system_control import router as system_router
from app.core.market.scheduler import (
    start_candle_scheduler,
    start_vix_scheduler,
    initialize_vix_data,
    stop_scheduler,
)
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 🔹 Startup
    logger.info("🚀 App starting")
    
    # Skip heavy initialization for Phase 1 testing
    # initialize_vix_data() can be called manually when needed
    
    # Start schedulers (optional for Phase 1)
    # start_candle_scheduler()
    # start_vix_scheduler()

    yield  # 👈 App runs here

    # 🔹 Shutdown
    logger.info("🛑 App shutting down")
    stop_scheduler()

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend directory
backend_dir = Path(__file__).parent.parent
env_path = backend_dir / ".env"
load_dotenv(dotenv_path=env_path, override=True)
logger.info(f"📝 Loading .env from: {env_path}")

app = FastAPI(
    title="AI ML Trading Backend",
    version="1.0.0",
    description="Backend engine for option spread strategies",
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

# Register routers
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
app.include_router(paper_mtm_router)

app.include_router(exit_router)
app.include_router(auto_exit_router)

app.include_router(system_router)