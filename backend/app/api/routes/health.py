"""
Health Monitoring API Routes
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.db.session import SessionLocal
from app.services.health_monitor import HealthMonitor, performance_tracker
from app.core.rate_limiter import zerodha_limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["Health"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/")
def health_check():
    """Simple health check"""
    return {
        "status": "healthy",
        "service": "FastTrade Backend"
    }


@router.get("/heartbeat")
def heartbeat(db: Session = Depends(get_db)):
    """Heartbeat with basic info"""
    monitor = HealthMonitor(db)
    return monitor.get_heartbeat()


@router.get("/full")
def full_health_status(db: Session = Depends(get_db)):
    """Comprehensive health status"""
    monitor = HealthMonitor(db)
    return monitor.get_full_health_status()


@router.get("/database")
def database_health(db: Session = Depends(get_db)):
    """Database connectivity check"""
    monitor = HealthMonitor(db)
    return monitor.check_database()


@router.get("/candles")
def candle_freshness(db: Session = Depends(get_db)):
    """Check candle data freshness"""
    monitor = HealthMonitor(db)
    return monitor.check_candle_freshness()


@router.get("/resources")
def system_resources(db: Session = Depends(get_db)):
    """System resource usage"""
    monitor = HealthMonitor(db)
    return monitor.check_system_resources()


@router.get("/performance")
def api_performance():
    """API endpoint performance stats"""
    return {
        "success": True,
        "endpoints": performance_tracker.get_all_stats()
    }


@router.get("/performance/{endpoint:path}")
def endpoint_performance(endpoint: str):
    """Performance stats for specific endpoint"""
    return {
        "success": True,
        "stats": performance_tracker.get_stats(endpoint)
    }


# ========== Rate Limiter Monitoring ==========

@router.get("/rate-limiter")
def get_rate_limiter_status():
    """
    Get current Zerodha API rate limiter status
    
    Returns:
        - tokens_available: Number of API tokens currently available
        - wait_time_ms: Milliseconds to wait before next request
        - cache_stats: Cache performance metrics
    """
    try:
        tokens = zerodha_limiter.global_limiter.tokens
        wait_time = zerodha_limiter.get_wait_time()
        cache_stats = zerodha_limiter.cache.get_stats()
        
        return {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "rate_limiter": {
                "tokens_available": round(tokens, 2),
                "max_tokens": zerodha_limiter.global_limiter.max_requests,
                "wait_time_seconds": round(wait_time, 3),
                "requests_per_second": zerodha_limiter.global_limiter.max_requests,
                "window_seconds": zerodha_limiter.global_limiter.window_seconds
            },
            "cache": cache_stats,
            "message": "Rate limiter active: 3 requests/second max"
        }
    except Exception as e:
        logger.error(f"Error fetching rate limiter status: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch rate limiter status")


@router.get("/cache-stats")
def get_cache_stats():
    """Get detailed cache statistics"""
    try:
        stats = zerodha_limiter.cache.get_stats()
        
        return {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "cache": {
                **stats,
                "ttl_seconds": zerodha_limiter.cache.ttl_seconds
            }
        }
    except Exception as e:
        logger.error(f"Error fetching cache stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch cache stats")


@router.post("/run-migrations")
def run_migrations():
    """Manually run DB column migrations — safe to call multiple times."""
    from app.db.session import engine
    from app.db.init_db import _MIGRATIONS_COMMON
    from sqlalchemy import text

    results = []
    for stmt in _MIGRATIONS_COMMON:
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
            results.append({"stmt": stmt[:60], "status": "applied"})
        except Exception as e:
            results.append({"stmt": stmt[:60], "status": "skipped", "reason": str(e)})
    return {"status": "done", "results": results}


@router.post("/backup-now")
def trigger_backup():
    """Manually trigger DB backup to cloud storage."""
    from app.db.r2_backup import backup_to_r2, _configured
    if not _configured():
        return {"status": "skipped", "reason": "BACKUP_BUCKET_NAME not configured"}
    ok = backup_to_r2()
    return {"status": "ok" if ok else "failed"}
