"""
Broker capabilities and status API.

GET /broker/capabilities        — what the active broker supports
GET /broker/capabilities/{name} — what a specific broker supports
GET /broker/list                — all registered brokers
GET /broker/data-status         — current data broker + candle freshness
"""
import logging
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException

from app.core.broker.registry import (
    BrokerUnsupportedError,
    get_active_broker,
    get_data_broker,
    get_registry,
)
from app.core.market.provider import get_broker_info
from app.core.execution.factory import get_broker_capabilities
from app.core.auth import require_authenticated_user

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


@router.get("/token-status")
def broker_token_status() -> Dict[str, Any]:
    """
    Check whether an active, VALID broker access token exists.
    Checks DB first, then env. Also does a lightweight liveness ping to confirm
    the token actually works (not just present). Safe to call when token is missing.
    """
    import os
    active_broker = get_active_broker()
    has_token = False
    token_valid = False
    source = "none"
    login_url: str | None = None
    error: str | None = None

    # ── 1. Find a token (DB or env) ────────────────────────────────────────
    raw_token: str | None = None

    if active_broker == "ZERODHA":
        try:
            from app.db.session import SessionLocal
            from app.core.broker.zerodha.oauth import get_active_session
            db = SessionLocal()
            try:
                session = get_active_session(db)
                if session:
                    raw_token = session.access_token
                    source = "db"
            finally:
                db.close()
        except Exception as exc:
            logger.warning("token-status Zerodha DB check failed: %s", exc)
        if not raw_token:
            raw_token = os.getenv("ZERODHA_ACCESS_TOKEN", "") or None
            if raw_token:
                source = "env"
        try:
            api_key = os.getenv("ZERODHA_API_KEY", "")
            if api_key:
                from kiteconnect import KiteConnect
                login_url = KiteConnect(api_key=api_key).login_url()
        except Exception:
            pass

    elif active_broker == "INDMONEY":
        try:
            from app.db.session import SessionLocal
            from app.db.models_indmoney import INDMoneySession
            from datetime import datetime
            db = SessionLocal()
            try:
                session = (
                    db.query(INDMoneySession)
                    .filter(INDMoneySession.is_active == 1)
                    .order_by(INDMoneySession.created_at.desc())
                    .first()
                )
                if session:
                    exp = session.expires_at
                    if exp and exp.tzinfo:
                        exp = exp.replace(tzinfo=None)
                    if exp is None or exp > datetime.utcnow():
                        raw_token = session.access_token
                        source = "db"
            finally:
                db.close()
        except Exception as exc:
            logger.warning("token-status INDMoney DB check failed: %s", exc)
        if not raw_token:
            raw_token = os.getenv("INDMONEY_ACCESS_TOKEN", "") or None
            if raw_token:
                source = "env"

    has_token = bool(raw_token)

    # ── 2. Liveness ping — confirm token actually works ────────────────────
    if has_token:
        if active_broker == "INDMONEY":
            # INDMoney: ping with a stock (RELIANCE) — indices return empty {} from LTP endpoint.
            try:
                from app.core.broker.indstocks.market_data import fetch_ltp_by_symbol
                result = fetch_ltp_by_symbol(["RELIANCE"])
                token_valid = bool(result)
            except Exception as exc:
                token_valid = False
                error = str(exc)
                logger.warning("token-status liveness ping failed for INDMONEY: %s", exc)
        else:
            try:
                if active_broker == "ZERODHA":
                    from app.core.broker.zerodha import client as zc
                    zc._kite = None  # force fresh client with current token
                    kite = zc.get_kite_client()
                    kite.profile()   # lightweight call — just fetches user profile
                    token_valid = True
            except Exception as exc:
                token_valid = False
                error = str(exc)
                logger.warning("token-status liveness ping failed for %s: %s", active_broker, exc)

    return {
        "has_token": has_token and token_valid,  # only true if token exists AND works
        "token_found": has_token,                # token string exists (may be expired)
        "token_valid": token_valid,              # liveness ping passed
        "source": source,
        "broker": active_broker,
        "login_url": login_url,
        "error": error,
    }


@router.post("/set-token")
def set_broker_token(
    access_token: str = Body(..., embed=True),
    current_user=Depends(require_authenticated_user),
) -> Dict[str, Any]:
    """
    Activate a broker access token pasted by the user.
    Supports ZERODHA and INDMONEY. Stores in DB so all schedulers pick it up immediately.
    """
    if not access_token or len(access_token) < 10:
        raise HTTPException(status_code=400, detail="Invalid access token")

    active_broker = get_active_broker()

    try:
        if active_broker == "ZERODHA":
            from app.db.session import SessionLocal
            from app.core.broker.zerodha.oauth import activate_access_token
            from app.core.broker.zerodha import client as zerodha_client
            db = SessionLocal()
            try:
                activate_access_token(db, access_token.strip(), user_id=current_user.get("username"))
            finally:
                db.close()
            zerodha_client._kite = None
            # Reset WS circuit breaker so quotes resume immediately
            from app.api.routes import websocket_routes as _ws
            _ws._broker_unavailable = False
            _ws._broker_unavailable_until = 0.0

        elif active_broker == "INDMONEY":
            from app.db.session import SessionLocal
            from app.db.models_indmoney import INDMoneySession
            from app.core.broker.indstocks import market_data as ind_md
            from datetime import timedelta
            from app.core.utils.time import now_ist
            db = SessionLocal()
            try:
                db.query(INDMoneySession).filter(INDMoneySession.is_active == 1).update({"is_active": 0})
                existing = db.query(INDMoneySession).filter(
                    INDMoneySession.access_token == access_token.strip()
                ).first()
                if existing:
                    existing.is_active = 1
                    existing.expires_at = now_ist() + timedelta(days=1)
                else:
                    db.add(INDMoneySession(
                        access_token=access_token.strip(),
                        client_id=current_user.get("username"),
                        expires_at=now_ist() + timedelta(days=1),
                        is_active=1,
                    ))
                db.commit()
            finally:
                db.close()
            ind_md._cached_token = ""
            ind_md._cached_token_expires = 0.0

        else:
            raise HTTPException(status_code=400, detail=f"Token setup not supported for broker: {active_broker}")

        logger.info("Broker token set via UI by %s for %s", current_user.get("username"), active_broker)
        return {"success": True, "message": f"{active_broker} token activated successfully"}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("set-token failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
