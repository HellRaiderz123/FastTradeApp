"""
Health Monitoring API Routes
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.health_monitor import HealthMonitor, performance_tracker

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
