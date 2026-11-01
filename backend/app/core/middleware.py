"""
Middleware Configuration Module

Extracted from main.py to reduce complexity.
Handles CORS, request tracking, and other middleware setup.
"""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


def setup_cors_middleware(app: "FastAPI") -> None:
    """
    Configure CORS middleware for the FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    raw_cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
    
    default_cors_origins = {
        "http://localhost:3000",      # Frontend dev server
        "http://localhost:5173",      # Vite dev server
        "http://localhost:5174",      # Alternative Vite port
        "http://localhost:8081",      # Expo/web dev server
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:8081",
        "http://192.168.1.104:3000",
        "http://192.168.1.104:5173",
        "http://192.168.1.104:8081",
        "https://fast-trade-app-59we.vercel.app",
    }
    
    extra_cors_origins = {
        origin.strip().rstrip("/")
        for origin in raw_cors_origins.split(",")
        if origin.strip()
    }
    
    cors_allowed_origins = sorted(
        origin.rstrip("/") for origin in (default_cors_origins | extra_cors_origins)
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allowed_origins,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+)(:\d+)?$|https://fast-trade[a-z0-9-]*\.vercel\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    logger.info("✅ CORS middleware enabled for: %s", ", ".join(cors_allowed_origins[:5]) + "...")


def setup_request_tracking_middleware(app: "FastAPI") -> None:
    """
    Configure request ID and performance tracking middleware.
    
    Args:
        app: FastAPI application instance
    """
    from app.core.logging_config import set_request_id
    from app.services.health_monitor import performance_tracker

    @app.middleware("http")
    async def add_request_id_and_track_performance(request: Request, call_next):
        """Add request ID to context and track API performance."""
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
            logger.error(
                "Request failed: %s (%.2fms)",
                request.url.path,
                duration_ms,
                exc_info=True
            )
            raise


def setup_all_middleware(app: "FastAPI") -> None:
    """
    Configure all middleware for the FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    setup_cors_middleware(app)
    setup_request_tracking_middleware(app)
    logger.info("✅ All middleware configured")
