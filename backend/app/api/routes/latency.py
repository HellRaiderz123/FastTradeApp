"""
Broker Latency API — mirrors OpenAlgo's /latency blueprint.
"""
from __future__ import annotations

import csv
import io
from datetime import timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models_latency import BrokerLatency

router = APIRouter(prefix="/latency", tags=["Latency"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _fmt_ist(dt) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        from datetime import timezone, timedelta
        dt = dt.replace(tzinfo=timezone.utc)
    from datetime import timedelta
    ist = dt.astimezone(timezone(timedelta(hours=5, minutes=30)))
    return ist.strftime("%d-%m-%Y %I:%M:%S %p")


def _row_dict(r: BrokerLatency) -> dict:
    return {
        "id": r.id,
        "timestamp": _fmt_ist(r.timestamp),
        "order_id": r.order_id,
        "broker": r.broker,
        "symbol": r.symbol,
        "order_type": r.order_type,
        "rtt_ms": round(r.rtt_ms, 2),
        "overhead_ms": round(r.overhead_ms, 2),
        "total_latency_ms": round(r.total_latency_ms, 2),
        "status": r.status,
        "error": r.error,
    }


@router.get("/logs")
def get_logs(limit: int = Query(100, le=1000), db: Session = Depends(get_db)):
    return [_row_dict(r) for r in BrokerLatency.recent(db, limit=limit)]


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    return BrokerLatency.stats(db)


@router.get("/export")
def export_csv(db: Session = Depends(get_db)):
    rows = BrokerLatency.recent(db, limit=10_000)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "Date & Time (IST)", "Broker", "Order ID", "Symbol", "Order Type",
        "Broker RTT (ms)", "Platform Overhead (ms)", "Total Latency (ms)",
        "Status", "Error",
    ])
    for r in rows:
        w.writerow([
            _fmt_ist(r.timestamp), r.broker or "N/A", r.order_id,
            r.symbol or "N/A", r.order_type,
            round(r.rtt_ms, 2), round(r.overhead_ms, 2), round(r.total_latency_ms, 2),
            r.status, r.error or "",
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=latency_logs.csv"},
    )
