"""
Health Monitoring System
"""

import logging
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.utils.time import now_ist

logger = logging.getLogger(__name__)


class HealthMonitor:
    """System health monitoring"""
    
    def __init__(self, db: Session):
        self.db = db
        self.start_time = time.time()
    
    def get_full_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status"""
        return {
            "status": "healthy",
            "timestamp": now_ist().isoformat(),
            "uptime_seconds": self.get_uptime(),
            "database": self.check_database(),
            "candle_freshness": self.check_candle_freshness(),
            "api_latency": self.check_api_latency(),
            "system_resources": self.check_system_resources(),
            "trading_status": self.check_trading_status()
        }
    
    def get_uptime(self) -> float:
        """Get system uptime in seconds"""
        return time.time() - self.start_time
    
    def check_database(self) -> Dict[str, Any]:
        """Check database connectivity and health"""
        try:
            start = time.time()
            
            # Simple query
            result = self.db.execute(text("SELECT 1")).scalar()
            
            latency = (time.time() - start) * 1000  # ms
            
            # Check connection pool
            pool = self.db.get_bind().pool
            pool_status = {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "overflow": pool.overflow(),
                "checked_out": pool.checkedout()
            }
            
            return {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "pool": pool_status
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def check_candle_freshness(self) -> Dict[str, Any]:
        """Check if candle data is fresh (< 1 hour old)"""
        try:
            from app.db.models import Candle
            
            # Get latest candle
            latest = (
                self.db.query(Candle)
                .order_by(Candle.timestamp.desc())
                .first()
            )
            
            if not latest:
                return {
                    "status": "warning",
                    "message": "No candle data found"
                }
            
            # Check age
            age = now_ist() - latest.timestamp
            age_minutes = age.total_seconds() / 60
            
            is_fresh = age_minutes < 60
            
            return {
                "status": "fresh" if is_fresh else "stale",
                "latest_candle": latest.timestamp.isoformat(),
                "age_minutes": round(age_minutes, 1),
                "symbol": latest.symbol
            }
            
        except Exception as e:
            logger.error(f"Candle freshness check failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def check_api_latency(self) -> Dict[str, Any]:
        """Check API response latency"""
        try:
            # Test database query
            start = time.time()
            self.db.execute(text("SELECT COUNT(*) FROM strategy_configs")).scalar()
            db_latency = (time.time() - start) * 1000
            
            return {
                "status": "healthy" if db_latency < 100 else "slow",
                "database_ms": round(db_latency, 2)
            }
            
        except Exception as e:
            logger.error(f"API latency check failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def check_system_resources(self) -> Dict[str, Any]:
        """Check CPU, memory, disk usage"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "status": "healthy",
                "cpu_percent": cpu_percent,
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "percent": memory.percent
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "percent": disk.percent
                }
            }
            
        except Exception as e:
            logger.error(f"Resource check failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def check_trading_status(self) -> Dict[str, Any]:
        """Check if trading is enabled and system state"""
        try:
            from app.db.models_control import SystemControl
            
            system = self.db.query(SystemControl).first()
            
            if not system:
                return {
                    "status": "unknown",
                    "trading_enabled": False
                }
            
            return {
                "status": "active" if system.trading_enabled else "paused",
                "trading_enabled": system.trading_enabled
            }
            
        except Exception as e:
            logger.error(f"Trading status check failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def get_heartbeat(self) -> Dict[str, Any]:
        """Simple heartbeat check"""
        return {
            "status": "alive",
            "timestamp": now_ist().isoformat(),
            "uptime_seconds": self.get_uptime()
        }


class PerformanceTracker:
    """Track API endpoint performance"""
    
    def __init__(self):
        self.request_times: Dict[str, list] = {}
    
    def record_request(self, endpoint: str, duration_ms: float):
        """Record request duration"""
        if endpoint not in self.request_times:
            self.request_times[endpoint] = []
        
        self.request_times[endpoint].append({
            "duration_ms": duration_ms,
            "timestamp": time.time()
        })
        
        # Keep only last 100 requests per endpoint
        if len(self.request_times[endpoint]) > 100:
            self.request_times[endpoint].pop(0)
    
    def get_stats(self, endpoint: str) -> Dict[str, Any]:
        """Get performance stats for endpoint"""
        if endpoint not in self.request_times or not self.request_times[endpoint]:
            return {
                "endpoint": endpoint,
                "requests": 0
            }
        
        durations = [r["duration_ms"] for r in self.request_times[endpoint]]
        
        return {
            "endpoint": endpoint,
            "requests": len(durations),
            "avg_ms": round(sum(durations) / len(durations), 2),
            "min_ms": round(min(durations), 2),
            "max_ms": round(max(durations), 2),
            "p95_ms": round(sorted(durations)[int(len(durations) * 0.95)], 2) if len(durations) > 1 else 0
        }
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get stats for all endpoints"""
        return {
            endpoint: self.get_stats(endpoint)
            for endpoint in self.request_times.keys()
        }


# Global performance tracker
performance_tracker = PerformanceTracker()
