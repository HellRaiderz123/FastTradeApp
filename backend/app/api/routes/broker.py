"""
Broker capabilities and status API.

GET /broker/capabilities        — what the active broker supports
GET /broker/capabilities/{name} — what a specific broker supports
GET /broker/list                — all registered brokers
GET /broker/data-status         — current data broker + candle freshness
"""
import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.core.broker.registry import (
    BrokerUnsupportedError,
    get_active_broker,
    get_data_broker,
    get_registry,
)
from app.core.market.provider import get_broker_info
from app.core.execution.factory import get_broker_capabilities

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/broker", tags=["Broker"])


@router.get("/capabilities")
def active_broker_capabilities() -> Dict[str, Any]:
    """Return capabilities of the currently active execution broker."""
    broker = get_active_broker()
    return get_broker_capabilities(broker)


@router.get("/capabilities/{broker_name}")
def broker_capabilities(broker_name: str) -> Dict[str, Any]:
    """Return capabilities of a specific broker by name."""
    try:
        caps = get_registry().get(broker_name.upper())
        return {
            "broker": caps.name,
            "display_name": caps.display_name,
            "historical_data": caps.historical_data,
            "live_ltp": caps.live_ltp,
            "live_quotes": caps.live_quotes,
            "market_depth": caps.market_depth,
            "order_placement": caps.order_placement,
            "order_cancellation": caps.order_cancellation,
            "gtt_orders": caps.gtt_orders,
            "margin_calculation": caps.margin_calculation,
            "positions": caps.positions,
            "holdings": caps.holdings,
            "order_book": caps.order_book,
            "funds": caps.funds,
            "unsupported_hints": caps.unsupported_hints,
        }
    except BrokerUnsupportedError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/list")
def list_brokers() -> Dict[str, Any]:
    """List all registered brokers and their support status."""
    reg = get_registry()
    active = get_active_broker()
    data = get_data_broker()
    brokers = []
    for name in reg.list_brokers():
        caps = reg.get(name)
        brokers.append({
            "name": name,
            "display_name": caps.display_name,
            "is_active_execution": name == active,
            "is_active_data": name == data,
            "order_placement": caps.order_placement,
            "historical_data": caps.historical_data,
        })
    return {
        "active_execution_broker": active,
        "active_data_broker": data,
        "brokers": brokers,
    }


@router.get("/data-status")
def data_broker_status() -> Dict[str, Any]:
    """Return data broker info + candle freshness check."""
    info = get_broker_info()

    # Check candle freshness
    try:
        from app.db.session import SessionLocal
        from app.db.models_candles import Candle15m
        from sqlalchemy import func

        db = SessionLocal()
        try:
            latest = (
                db.query(func.max(Candle15m.timestamp))
                .filter(Candle15m.symbol == "NIFTY")
                .scalar()
            )
            info["latest_15m_candle"] = latest.isoformat() if latest else None
            info["candles_stale"] = True
            if latest:
                from app.core.utils.time import now_ist
                from datetime import timedelta
                age_hours = (now_ist().replace(tzinfo=None) - latest).total_seconds() / 3600
                info["candle_age_hours"] = round(age_hours, 1)
                # Stale if older than 2 hours during market hours
                info["candles_stale"] = age_hours > 2
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Could not check candle freshness: %s", exc)
        info["candle_check_error"] = str(exc)

    return info
