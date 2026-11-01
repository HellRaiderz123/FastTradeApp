"""
Metrics Module — Prometheus-compatible metrics endpoint.

Provides application metrics for monitoring and observability.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@dataclass
class MetricValue:
    """Single metric value with labels."""
    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    metric_type: str = "gauge"  # gauge, counter, histogram
    help_text: str = ""


class MetricsCollector:
    """
    Collects and exposes application metrics.
    
    Thread-safe singleton for collecting metrics from various parts of the app.
    """

    _instance: Optional["MetricsCollector"] = None
    _lock = Lock()

    def __new__(cls) -> "MetricsCollector":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        """Initialize metrics storage."""
        self._counters: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._gauges: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._histograms: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
        self._histogram_buckets = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        self._start_time = time.time()
        self._lock = Lock()

    def inc_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric."""
        label_key = self._labels_to_key(labels)
        with self._lock:
            self._counters[name][label_key] += value

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric value."""
        label_key = self._labels_to_key(labels)
        with self._lock:
            self._gauges[name][label_key] = value

    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a histogram observation."""
        label_key = self._labels_to_key(labels)
        with self._lock:
            self._histograms[name][label_key].append(value)
            # Keep only last 1000 observations per label set
            if len(self._histograms[name][label_key]) > 1000:
                self._histograms[name][label_key] = self._histograms[name][label_key][-1000:]

    def _labels_to_key(self, labels: Optional[Dict[str, str]]) -> str:
        """Convert labels dict to a hashable key."""
        if not labels:
            return ""
        return ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))

    def _key_to_labels(self, key: str) -> str:
        """Convert key back to Prometheus label format."""
        return "{" + key + "}" if key else ""

    def get_prometheus_output(self) -> str:
        """Generate Prometheus-compatible text output."""
        lines: List[str] = []
        
        # Add uptime gauge
        uptime = time.time() - self._start_time
        lines.append("# HELP fasttrade_uptime_seconds Time since application start")
        lines.append("# TYPE fasttrade_uptime_seconds gauge")
        lines.append(f"fasttrade_uptime_seconds {uptime:.2f}")
        lines.append("")

        # Counters
        with self._lock:
            for name, label_values in self._counters.items():
                lines.append(f"# HELP {name} Counter metric")
                lines.append(f"# TYPE {name} counter")
                for label_key, value in label_values.items():
                    labels = self._key_to_labels(label_key)
                    lines.append(f"{name}{labels} {value}")
                lines.append("")

            # Gauges
            for name, label_values in self._gauges.items():
                lines.append(f"# HELP {name} Gauge metric")
                lines.append(f"# TYPE {name} gauge")
                for label_key, value in label_values.items():
                    labels = self._key_to_labels(label_key)
                    lines.append(f"{name}{labels} {value}")
                lines.append("")

            # Histograms
            for name, label_values in self._histograms.items():
                lines.append(f"# HELP {name} Histogram metric")
                lines.append(f"# TYPE {name} histogram")
                for label_key, observations in label_values.items():
                    if not observations:
                        continue
                    labels = self._key_to_labels(label_key)
                    
                    # Calculate bucket counts
                    sorted_obs = sorted(observations)
                    total = len(sorted_obs)
                    sum_val = sum(sorted_obs)
                    
                    for bucket in self._histogram_buckets:
                        count = sum(1 for o in sorted_obs if o <= bucket)
                        bucket_labels = label_key + f',le="{bucket}"' if label_key else f'le="{bucket}"'
                        lines.append(f"{name}_bucket{{{bucket_labels}}} {count}")
                    
                    inf_labels = label_key + ',le="+Inf"' if label_key else 'le="+Inf"'
                    lines.append(f"{name}_bucket{{{inf_labels}}} {total}")
                    lines.append(f"{name}_sum{labels} {sum_val:.6f}")
                    lines.append(f"{name}_count{labels} {total}")
                lines.append("")

        return "\n".join(lines)

    def get_json_metrics(self) -> Dict[str, Any]:
        """Get metrics as JSON for API consumption."""
        with self._lock:
            return {
                "uptime_seconds": time.time() - self._start_time,
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    name: {
                        label: {
                            "count": len(obs),
                            "sum": sum(obs) if obs else 0,
                            "avg": sum(obs) / len(obs) if obs else 0,
                            "min": min(obs) if obs else 0,
                            "max": max(obs) if obs else 0,
                        }
                        for label, obs in label_values.items()
                    }
                    for name, label_values in self._histograms.items()
                },
                "collected_at": datetime.utcnow().isoformat(),
            }


# Global metrics collector instance
metrics = MetricsCollector()


def collect_system_metrics() -> None:
    """Collect system-level metrics (CPU, memory, etc.)."""
    try:
        import psutil
        
        # CPU
        metrics.set_gauge("fasttrade_cpu_percent", psutil.cpu_percent(interval=0.1))
        
        # Memory
        mem = psutil.virtual_memory()
        metrics.set_gauge("fasttrade_memory_used_bytes", mem.used)
        metrics.set_gauge("fasttrade_memory_total_bytes", mem.total)
        metrics.set_gauge("fasttrade_memory_percent", mem.percent)
        
        # Disk
        disk = psutil.disk_usage("/")
        metrics.set_gauge("fasttrade_disk_used_bytes", disk.used)
        metrics.set_gauge("fasttrade_disk_total_bytes", disk.total)
        metrics.set_gauge("fasttrade_disk_percent", disk.percent)
        
    except Exception as e:
        logger.debug("Failed to collect system metrics: %s", e)


def collect_db_metrics() -> None:
    """Collect database metrics."""
    try:
        from app.db.session import SessionLocal, engine
        
        # Connection pool stats
        pool = engine.pool
        metrics.set_gauge("fasttrade_db_pool_size", pool.size())
        metrics.set_gauge("fasttrade_db_pool_checkedin", pool.checkedin())
        metrics.set_gauge("fasttrade_db_pool_checkedout", pool.checkedout())
        metrics.set_gauge("fasttrade_db_pool_overflow", pool.overflow())
        
    except Exception as e:
        logger.debug("Failed to collect DB metrics: %s", e)


def collect_broker_metrics() -> None:
    """Collect broker-related metrics."""
    try:
        from app.core.broker.interface import get_broker_manager
        
        manager = get_broker_manager()
        status = manager.get_status()
        
        # Broker status
        metrics.set_gauge(
            "fasttrade_broker_active",
            1,
            {"broker": status.get("active_broker", "unknown")}
        )
        
        # Adapters loaded
        metrics.set_gauge(
            "fasttrade_broker_adapters_loaded",
            len(status.get("adapters_loaded", []))
        )
        
    except Exception as e:
        logger.debug("Failed to collect broker metrics: %s", e)


def collect_trading_metrics() -> None:
    """Collect trading-related metrics."""
    try:
        from app.db.session import SessionLocal
        from app.db.models_intent import ExecutionIntent
        from sqlalchemy import func
        
        db = SessionLocal()
        try:
            # Open positions count
            open_count = (
                db.query(func.count(ExecutionIntent.id))
                .filter(
                    ExecutionIntent.status == "EXECUTED",
                    ExecutionIntent.closed_at.is_(None)
                )
                .scalar() or 0
            )
            metrics.set_gauge("fasttrade_positions_open", open_count)
            
            # Today's trades
            from datetime import date
            today_count = (
                db.query(func.count(ExecutionIntent.id))
                .filter(
                    ExecutionIntent.status == "EXECUTED",
                    func.date(ExecutionIntent.created_at) == date.today()
                )
                .scalar() or 0
            )
            metrics.set_gauge("fasttrade_trades_today", today_count)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.debug("Failed to collect trading metrics: %s", e)


def collect_ai_job_metrics() -> None:
    """Collect AI analysis job metrics."""
    try:
        from app.services.trading_agents import _jobs, _jobs_lock
        
        with _jobs_lock:
            total = len(_jobs)
            running = sum(1 for j in _jobs.values() if j.get("status") == "RUNNING")
            completed = sum(1 for j in _jobs.values() if j.get("status") == "COMPLETED")
            failed = sum(1 for j in _jobs.values() if j.get("status") == "FAILED")
            
        metrics.set_gauge("fasttrade_ai_jobs_total", total)
        metrics.set_gauge("fasttrade_ai_jobs_running", running)
        metrics.set_gauge("fasttrade_ai_jobs_completed", completed)
        metrics.set_gauge("fasttrade_ai_jobs_failed", failed)
        
    except Exception as e:
        logger.debug("Failed to collect AI job metrics: %s", e)


def collect_all_metrics() -> None:
    """Collect all application metrics."""
    collect_system_metrics()
    collect_db_metrics()
    collect_broker_metrics()
    collect_trading_metrics()
    collect_ai_job_metrics()


# ─────────────────────────────────────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/", response_class=Response)
def get_prometheus_metrics():
    """
    Prometheus-compatible metrics endpoint.
    
    Returns metrics in Prometheus text format for scraping.
    """
    collect_all_metrics()
    output = metrics.get_prometheus_output()
    return Response(
        content=output,
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )


@router.get("/json")
def get_json_metrics():
    """
    JSON metrics endpoint.
    
    Returns metrics in JSON format for API consumption.
    """
    collect_all_metrics()
    return metrics.get_json_metrics()


@router.get("/health")
def metrics_health():
    """Health check for metrics endpoint."""
    return {
        "status": "healthy",
        "uptime_seconds": time.time() - metrics._start_time,
    }
