"""
Health Monitoring API Routes
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.db.session import SessionLocal
from app.services.health_monitor import HealthMonitor, performance_tracker
from app.core.rate_limiter import broker_limiter

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


@router.get("/ready")
def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness check — verifies all critical dependencies are available.
    Returns 503 if any dependency is unhealthy.
    """
    from fastapi import HTTPException
    from sqlalchemy import text
    
    checks = {
        "database": False,
        "broker": False,
        "scheduler": False,
    }
    errors = []
    
    # Check database
    try:
        db.execute(text("SELECT 1")).scalar()
        checks["database"] = True
    except Exception as e:
        errors.append(f"database: {e}")
    
    # Check broker
    try:
        from app.core.broker.interface import get_broker_manager
        manager = get_broker_manager()
        status = manager.get_status()
        checks["broker"] = bool(status.get("active_broker"))
    except Exception as e:
        errors.append(f"broker: {e}")
    
    # Check scheduler
    try:
        from app.core.market.scheduler import scheduler
        checks["scheduler"] = scheduler.running
    except Exception as e:
        errors.append(f"scheduler: {e}")
    
    all_ready = all(checks.values())
    
    result = {
        "ready": all_ready,
        "checks": checks,
    }
    
    if errors:
        result["errors"] = errors
    
    if not all_ready:
        raise HTTPException(status_code=503, detail=result)
    
    return result


@router.get("/heartbeat")
def heartbeat(db: Session = Depends(get_db)):
    """Heartbeat with basic info"""
    monitor = HealthMonitor(db)
    return monitor.get_heartbeat()


@router.get("/full")
def full_health_status(db: Session = Depends(get_db)):
    """Comprehensive health status including broker"""
    monitor = HealthMonitor(db)
    status = monitor.get_full_health_status()
    
    # Add broker status
    try:
        from app.core.broker.interface import get_broker_manager
        broker_status = get_broker_manager().get_status()
        status["broker"] = broker_status
    except Exception as e:
        status["broker"] = {"status": "error", "error": str(e)}
    
    return status


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
    Get current broker API rate limiter status.
    """
    try:
        from app.core.broker.registry import get_active_broker
        active_broker = get_active_broker()

        tokens = broker_limiter.global_limiter.tokens
        wait_time = broker_limiter.get_wait_time()
        cache_stats = broker_limiter.cache.get_stats()

        return {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "broker": active_broker,
            "rate_limiter": {
                "tokens_available": round(tokens, 2),
                "max_tokens": broker_limiter.global_limiter.max_requests,
                "wait_time_seconds": round(wait_time, 3),
                "requests_per_second": broker_limiter.global_limiter.max_requests,
                "window_seconds": broker_limiter.global_limiter.window_seconds,
            },
            "cache": cache_stats,
        }
    except Exception as e:
        logger.error(f"Error fetching rate limiter status: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch rate limiter status")


@router.get("/cache-stats")
def get_cache_stats():
    """Get detailed cache statistics"""
    try:
        stats = broker_limiter.cache.get_stats()

        return {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "cache": {
                **stats,
                "ttl_seconds": broker_limiter.cache.ttl_seconds,
            },
        }
    except Exception as e:
        logger.error(f"Error fetching cache stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch cache stats")


@router.get("/schedulers")
def scheduler_status():
    """List all registered APScheduler jobs and their next run times."""
    try:
        from app.core.market.scheduler import scheduler
        jobs = []
        for job in scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                "paused": job.next_run_time is None,
            })
        return {
            "scheduler_running": scheduler.running,
            "job_count": len(jobs),
            "jobs": sorted(jobs, key=lambda j: j["id"]),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-migrations")
def run_migrations():
    """Manually run DB column migrations + ensure all tables exist. Safe to call multiple times."""
    from app.db.session import engine
    from app.db.init_db import init_db, _MIGRATIONS_COMMON
    from sqlalchemy import text

    # Ensure all tables are created first
    try:
        init_db()
        table_status = "ok"
    except Exception as e:
        table_status = str(e)

    results = []
    for stmt in _MIGRATIONS_COMMON:
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
            results.append({"stmt": stmt[:60], "status": "applied"})
        except Exception as e:
            results.append({"stmt": stmt[:60], "status": "skipped", "reason": str(e)})
    return {"status": "done", "table_init": table_status, "results": results}


@router.post("/backup-now")
def trigger_backup():
    """Manually trigger DB backup to cloud storage."""
    from app.db.r2_backup import backup_to_r2, _configured
    if not _configured():
        return {"status": "skipped", "reason": "BACKUP_BUCKET_NAME not configured"}
    ok = backup_to_r2()
    return {"status": "ok" if ok else "failed"}


@router.post("/restore-now")
def trigger_restore():
    """Force restore DB from cloud storage (overwrites local)."""
    from app.db.r2_backup import restore_from_r2, _configured
    if not _configured():
        return {"status": "skipped", "reason": "BACKUP_BUCKET_NAME not configured"}
    ok = restore_from_r2(force=True)
    return {"status": "restored" if ok else "failed"}
