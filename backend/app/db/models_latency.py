"""
BrokerLatency — persists per-order latency records.

Columns mirror OpenAlgo's OrderLatency so the frontend can use the same
field names without translation.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Session

from app.db.models import Base


class BrokerLatency(Base):
    __tablename__ = "broker_latency"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Order identity
    order_id = Column(String(128), nullable=False, default="unknown")
    broker = Column(String(64), nullable=True, index=True)
    symbol = Column(String(64), nullable=True)
    order_type = Column(String(32), nullable=False)  # PLACE, MODIFY, CANCEL, QUOTES, …

    # Latency breakdown (ms)
    rtt_ms = Column(Float, nullable=False, default=0.0)        # broker HTTP round-trip
    overhead_ms = Column(Float, nullable=False, default=0.0)   # FastTrade processing
    total_latency_ms = Column(Float, nullable=False, default=0.0)

    status = Column(String(16), nullable=False, default="SUCCESS")  # SUCCESS | FAILED
    error = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_broker_latency_broker_ts", "broker", "timestamp"),
    )

    # ── class-level helpers ──────────────────────────────────────────────────

    @classmethod
    def log(
        cls,
        db: Session,
        *,
        order_id: str,
        broker: Optional[str],
        symbol: Optional[str],
        order_type: str,
        rtt_ms: float,
        overhead_ms: float,
        total_ms: float,
        status: str,
        error: Optional[str] = None,
    ) -> None:
        record = cls(
            order_id=order_id,
            broker=broker,
            symbol=symbol,
            order_type=order_type,
            rtt_ms=round(rtt_ms, 3),
            overhead_ms=round(overhead_ms, 3),
            total_latency_ms=round(total_ms, 3),
            status=status,
            error=error,
        )
        db.add(record)
        db.commit()

    @classmethod
    def recent(cls, db: Session, limit: int = 100) -> List["BrokerLatency"]:
        return (
            db.query(cls)
            .order_by(cls.timestamp.desc())
            .limit(limit)
            .all()
        )

    @classmethod
    def stats(cls, db: Session) -> Dict[str, Any]:
        rows = db.query(cls).all()
        if not rows:
            return {
                "total_orders": 0,
                "success_rate": 0.0,
                "failed_orders": 0,
                "avg_total": 0.0,
                "sla_150ms": 0.0,
                "broker_stats": {},
            }

        total = len(rows)
        failed = sum(1 for r in rows if r.status != "SUCCESS")
        success_rate = ((total - failed) / total) * 100
        avg_total = sum(r.total_latency_ms for r in rows) / total
        sla_150ms = (sum(1 for r in rows if r.total_latency_ms < 150) / total) * 100

        # Per-broker breakdown
        from collections import defaultdict
        import statistics

        broker_rows: Dict[str, list] = defaultdict(list)
        for r in rows:
            broker_rows[r.broker or "unknown"].append(r.total_latency_ms)

        broker_stats: Dict[str, Any] = {}
        for b, vals in broker_rows.items():
            sorted_vals = sorted(vals)
            n = len(sorted_vals)
            broker_stats[b] = {
                "total_orders": n,
                "avg_total": round(sum(vals) / n, 2),
                "p50_total": round(sorted_vals[int(n * 0.50)], 2),
                "p99_total": round(sorted_vals[min(int(n * 0.99), n - 1)], 2),
                "sla_150ms": round(
                    (sum(1 for v in vals if v < 150) / n) * 100, 1
                ),
            }

        return {
            "total_orders": total,
            "success_rate": round(success_rate, 1),
            "failed_orders": failed,
            "avg_total": round(avg_total, 2),
            "sla_150ms": round(sla_150ms, 1),
            "broker_stats": broker_stats,
        }
