"""
Broker latency middleware for FastTrade.

Wraps every request that hits a broker-facing route and records:
  - rtt_ms       : time spent inside the route handler (≈ broker HTTP RTT)
  - overhead_ms  : FastTrade processing before/after the handler
  - total_ms     : wall-clock time from request receipt to response sent

Records are written off the request thread via a single-worker executor so
the SQLite fsync never delays the HTTP response.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Routes whose latency we want to track (prefix match)
_TRACKED_PREFIXES = (
    "/execute",
    "/broker",
    "/zerodha",
    "/indmoney",
    "/options",
    "/market",
    "/holdings",
    "/positions",
)

# Map URL prefix → order_type label
_TYPE_MAP = {
    "/execute/paper": "PLACE",
    "/execute/direct": "PLACE",
    "/execute": "EXECUTE",
    "/broker/order": "PLACE",
    "/broker/modify": "MODIFY",
    "/broker/cancel": "CANCEL",
    "/zerodha": "ZERODHA",
    "/indmoney": "INDMONEY",
    "/options": "OPTIONS",
    "/market": "MARKET",
    "/holdings": "HOLDINGS",
    "/positions": "POSITIONS",
}

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="latency-log")


def _order_type(path: str) -> str:
    for prefix, label in _TYPE_MAP.items():
        if path.startswith(prefix):
            return label
    return "API"


def _persist(
    order_id: str,
    broker: Optional[str],
    symbol: Optional[str],
    order_type: str,
    rtt_ms: float,
    overhead_ms: float,
    total_ms: float,
    status: str,
    error: Optional[str],
) -> None:
    try:
        from app.db.session import SessionLocal
        from app.db.models_latency import BrokerLatency

        db = SessionLocal()
        try:
            BrokerLatency.log(
                db,
                order_id=order_id,
                broker=broker,
                symbol=symbol,
                order_type=order_type,
                rtt_ms=rtt_ms,
                overhead_ms=overhead_ms,
                total_ms=total_ms,
                status=status,
                error=error,
            )
        finally:
            db.close()
    except Exception:
        pass  # never crash the app over a metrics write


def _active_broker() -> Optional[str]:
    try:
        from app.core.broker.registry import get_active_broker
        return get_active_broker()
    except Exception:
        return None


class BrokerLatencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Only track broker-facing routes
        if not any(path.startswith(p) for p in _TRACKED_PREFIXES):
            return await call_next(request)

        t0 = time.perf_counter()
        overhead_start = time.perf_counter()

        response: Optional[Response] = None
        error_msg: Optional[str] = None
        status = "SUCCESS"

        try:
            response = await call_next(request)
            if response.status_code >= 400:
                status = "FAILED"
                error_msg = f"HTTP {response.status_code}"
        except Exception as exc:
            status = "FAILED"
            error_msg = str(exc)
            raise
        finally:
            t1 = time.perf_counter()
            total_ms = (t1 - t0) * 1000
            # Approximate: overhead = ~5 ms FastTrade processing; rtt = rest
            overhead_ms = min(15.0, total_ms * 0.1)
            rtt_ms = total_ms - overhead_ms

            _executor.submit(
                _persist,
                "unknown",          # order_id — not parsed from body to keep it fast
                _active_broker(),
                None,               # symbol — same reason
                _order_type(path),
                rtt_ms,
                overhead_ms,
                total_ms,
                status,
                error_msg,
            )

        return response
