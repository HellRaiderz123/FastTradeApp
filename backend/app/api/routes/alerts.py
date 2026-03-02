"""
Alert Rules API
Create, manage, and evaluate alert rules for price-based triggers.
Includes ML signal scanning for automated buy/sell alerts.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.db.session import SessionLocal
from app.db.models import AlertRule
from app.db.multi_asset_repo import (
    create_alert_rule,
    list_active_alerts,
    get_alert_rule,
    update_alert_rule,
    mark_alert_triggered,
)
from app.core.utils.time import now_ist
from app.services.notifications import get_notification_service, NotificationType, NotificationPriority
from app.services.zerodha import KiteConnectService

router = APIRouter(prefix="/alerts", tags=["alerts"])
logger = logging.getLogger(__name__)

# In-memory cache to avoid duplicate alerts within a time window
_last_ml_alerts: Dict[str, Dict[str, Any]] = {}  # symbol -> {signal, confidence, timestamp}

kite_service = KiteConnectService()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class AlertCondition(BaseModel):
    operator: str = Field(..., description="above, below, above_or_equal, below_or_equal, equal")
    price: float = Field(..., gt=0)


class CreateAlertRequest(BaseModel):
    name: Optional[str] = None
    ticker: str
    alert_type: str = "PRICE"
    condition: AlertCondition
    is_enabled: bool = True
    is_recurring: bool = True
    notify_via: Optional[Dict[str, Any]] = None
    action_on_trigger: Optional[str] = None
    created_by: Optional[str] = None


class UpdateAlertRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    condition: Optional[AlertCondition] = None
    is_enabled: Optional[bool] = None
    is_recurring: Optional[bool] = None
    notify_via: Optional[Dict[str, Any]] = None
    action_on_trigger: Optional[str] = None


class AlertResponse(BaseModel):
    id: int
    name: str
    ticker: str
    alert_type: str
    condition: Dict[str, Any]
    is_enabled: bool
    is_recurring: bool
    notify_via: Dict[str, Any]
    trigger_count: int
    last_triggered_at: Optional[str]
    created_at: str


def _rule_to_response(rule: AlertRule) -> AlertResponse:
    return AlertResponse(
        id=rule.id,
        name=rule.name,
        ticker=rule.ticker,
        alert_type=rule.alert_type,
        condition=rule.condition,
        is_enabled=rule.is_enabled,
        is_recurring=rule.is_recurring,
        notify_via=rule.notify_via or {},
        trigger_count=rule.trigger_count or 0,
        last_triggered_at=rule.last_triggered_at.isoformat() if rule.last_triggered_at else None,
        created_at=rule.created_at.isoformat() if rule.created_at else now_ist().isoformat(),
    )


def _check_price_condition(operator: str, current_price: float, target_price: float) -> bool:
    if operator == "above":
        return current_price > target_price
    if operator == "below":
        return current_price < target_price
    if operator == "above_or_equal":
        return current_price >= target_price
    if operator == "below_or_equal":
        return current_price <= target_price
    if operator == "equal":
        return current_price == target_price
    raise ValueError(f"Unsupported operator: {operator}")


@router.post("/create")
def create_alert(request: CreateAlertRequest, db: Session = Depends(get_db)):
    try:
        name = request.name or f"{request.ticker} {request.condition.operator} {request.condition.price}"
        rule = create_alert_rule(
            db=db,
            name=name,
            ticker=request.ticker.upper(),
            alert_type=request.alert_type.upper(),
            condition=request.condition.dict(),
            is_enabled=request.is_enabled,
            notify_via=request.notify_via,
            action_on_trigger=request.action_on_trigger,
            created_by=request.created_by,
        )
        rule.is_recurring = request.is_recurring
        db.commit()
        db.refresh(rule)
        return {"success": True, "alert": _rule_to_response(rule).dict()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/list")
def list_alerts(ticker: Optional[str] = None, db: Session = Depends(get_db)):
    rules = list_active_alerts(db, ticker=ticker.upper() if ticker else None)
    return {"success": True, "count": len(rules), "alerts": [_rule_to_response(r).dict() for r in rules]}


@router.get("/{alert_id}")
def get_alert(alert_id: int, db: Session = Depends(get_db)):
    rule = get_alert_rule(db, alert_id)
    if not rule or rule.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"success": True, "alert": _rule_to_response(rule).dict()}


@router.patch("/{alert_id}")
def update_alert(alert_id: int, request: UpdateAlertRequest, db: Session = Depends(get_db)):
    rule = get_alert_rule(db, alert_id)
    if not rule or rule.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Alert not found")

    updates = request.dict(exclude_unset=True)
    if "condition" in updates and updates["condition"] is not None:
        updates["condition"] = updates["condition"].dict()

    updated = update_alert_rule(db, alert_id, **updates)
    return {"success": True, "alert": _rule_to_response(updated).dict()}


@router.post("/{alert_id}/enable")
def enable_alert(alert_id: int, db: Session = Depends(get_db)):
    updated = update_alert_rule(db, alert_id, is_enabled=True)
    return {"success": True, "alert": _rule_to_response(updated).dict()}


@router.post("/{alert_id}/disable")
def disable_alert(alert_id: int, db: Session = Depends(get_db)):
    updated = update_alert_rule(db, alert_id, is_enabled=False)
    return {"success": True, "alert": _rule_to_response(updated).dict()}


@router.delete("/{alert_id}")
def delete_alert(alert_id: int, db: Session = Depends(get_db)):
    rule = get_alert_rule(db, alert_id)
    if not rule or rule.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Alert not found")

    rule.deleted_at = now_ist()
    rule.is_enabled = False
    db.commit()
    return {"success": True, "message": "Alert deleted"}


@router.post("/evaluate")
def evaluate_alerts(ticker: Optional[str] = None, db: Session = Depends(get_db)):
    rules = list_active_alerts(db, ticker=ticker.upper() if ticker else None)
    if not rules:
        return {"success": True, "count": 0, "triggered": []}

    service = get_notification_service(db)
    triggered = []

    for rule in rules:
        if rule.alert_type.upper() != "PRICE":
            continue

        operator = (rule.condition or {}).get("operator")
        target_price = (rule.condition or {}).get("price")
        if not operator or target_price is None:
            continue

        quote = kite_service.get_full_quote(rule.ticker)
        current_price = quote.get("last_price") if quote else None
        if current_price is None:
            continue

        try:
            if _check_price_condition(operator, float(current_price), float(target_price)):
                mark_alert_triggered(db, rule.id)
                if not rule.is_recurring:
                    update_alert_rule(db, rule.id, is_enabled=False)

                service.notify_alert_triggered(
                    ticker=rule.ticker,
                    operator=operator,
                    target_price=float(target_price),
                    current_price=float(current_price),
                    alert_id=rule.id,
                )

                triggered.append({
                    "alert_id": rule.id,
                    "ticker": rule.ticker,
                    "current": current_price,
                    "target": target_price,
                    "operator": operator,
                })
        except Exception:
            continue

    return {"success": True, "count": len(triggered), "triggered": triggered}


# ============================
# ML SIGNAL SCANNING
# ============================

class ScanMLSignalsRequest(BaseModel):
    symbols: List[str] = Field(..., description="List of stock symbols to scan")
    min_confidence: int = Field(60, ge=30, le=100, description="Minimum confidence to trigger alert")
    cooldown_minutes: int = Field(15, ge=1, le=120, description="Minutes before re-alerting same symbol/signal")


@router.post("/scan-ml-signals")
def scan_ml_signals(request: ScanMLSignalsRequest, db: Session = Depends(get_db)):
    """
    Scan a list of symbols using ML predictions and return actionable BUY/SELL alerts.
    Creates notifications for new signals that exceed the confidence threshold.
    Uses an in-memory cooldown to avoid duplicate alerts.
    """
    from app.core.signals.ml_engine import ml_stock_signal

    triggered_alerts = []
    now = datetime.utcnow()

    for symbol in request.symbols[:30]:  # Cap at 30 symbols
        symbol = symbol.upper().strip()
        if not symbol:
            continue

        try:
            result = ml_stock_signal(db, symbol, timeframe="15m", use_ensemble=True)
        except Exception as e:
            logger.warning(f"ML scan failed for {symbol}: {e}")
            continue

        if not result or not isinstance(result, dict):
            continue

        signal = result.get("signal", "NO_TRADE")
        confidence = result.get("confidence", 0)
        bias = result.get("bias", "NEUTRAL")
        reason = result.get("reason", "")
        model_type = result.get("model_type", "unknown")
        indicators = result.get("indicators", {})

        # Only alert on actionable signals with sufficient confidence
        if signal not in ("BULLISH", "BEARISH") or confidence < request.min_confidence:
            continue

        # Check cooldown – skip if same signal was alerted recently
        cache_key = f"{symbol}:{signal}"
        prev = _last_ml_alerts.get(cache_key)
        if prev:
            elapsed = (now - prev["timestamp"]).total_seconds() / 60.0
            if elapsed < request.cooldown_minutes:
                continue  # Still in cooldown

        # New alert – update cache
        _last_ml_alerts[cache_key] = {
            "signal": signal,
            "confidence": confidence,
            "timestamp": now,
        }

        action = "BUY" if signal == "BULLISH" else "SELL"
        emoji = "🟢" if signal == "BULLISH" else "🔴"

        alert_data = {
            "symbol": symbol,
            "signal": signal,
            "action": action,
            "confidence": confidence,
            "bias": bias,
            "reason": reason,
            "model_type": model_type,
            "indicators": indicators,
            "timestamp": now.isoformat(),
        }

        # Create in-app notification
        try:
            service = get_notification_service(db)
            service._send_notification(
                type=NotificationType.ALERT_TRIGGERED,
                title=f"{emoji} {action} Signal – {symbol} ({confidence}%)",
                message=(
                    f"ML {model_type.upper()} model detected a {signal} signal for {symbol} "
                    f"with {confidence}% confidence.\n"
                    f"Bias: {bias}\n"
                    f"Reason: {reason}"
                ),
                priority=NotificationPriority.HIGH if confidence >= 75 else NotificationPriority.MEDIUM,
                metadata=alert_data,
            )
        except Exception as e:
            logger.warning(f"Failed to store notification for {symbol}: {e}")

        triggered_alerts.append(alert_data)

    return {
        "success": True,
        "count": len(triggered_alerts),
        "alerts": triggered_alerts,
        "scanned": min(len(request.symbols), 30),
        "timestamp": now.isoformat(),
    }


@router.get("/ml-signal-status")
def get_ml_signal_status():
    """Return current state of the ML alert cache (for debugging/UI)"""
    return {
        "success": True,
        "cached_alerts": {
            k: {
                "signal": v["signal"],
                "confidence": v["confidence"],
                "timestamp": v["timestamp"].isoformat(),
            }
            for k, v in _last_ml_alerts.items()
        },
        "count": len(_last_ml_alerts),
    }


@router.post("/clear-ml-cache")
def clear_ml_signal_cache():
    """Clear the ML alert cooldown cache"""
    _last_ml_alerts.clear()
    return {"success": True, "message": "ML signal cache cleared"}
