import logging
from datetime import datetime, time as dtime, timedelta
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models_candles import Candle1m, Candle5m, Candle15m, Candle1h, CandleDaily

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candles", tags=["Candles"])

# IST market hours
MARKET_OPEN = dtime(9, 15)
MARKET_CLOSE = dtime(15, 30)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _now_ist() -> datetime:
    """Get current time in IST."""
    from datetime import timezone
    IST = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(IST)


def _is_market_open() -> bool:
    """Check if Indian market is currently open (9:15-15:30 IST, Mon-Fri)."""
    now = _now_ist()
    if now.weekday() >= 5:  # Saturday/Sunday
        return False
    t = now.time()
    return MARKET_OPEN <= t <= MARKET_CLOSE


# Timeframe model mapping
TIMEFRAME_MODELS = {
    "1m": Candle1m,
    "5m": Candle5m,
    "15m": Candle15m,
    "1h": Candle1h,
    "daily": CandleDaily
}

# Timeframe to interval label mapping for provider
TIMEFRAME_TO_INTERVAL = {
    "1m": "1 Min",
    "5m": "5 Min",
    "15m": "15 Min",
    "1h": "1 Hour",
    "daily": "Day",
}


def _fetch_live_candles(symbol: str, timeframe: str, limit: int) -> List[Dict[str, Any]]:
    """
    Fetch live candles from broker API when market is open.
    Returns list of candle dicts with: timestamp/date, open, high, low, close, volume
    """
    try:
        from app.core.market.provider import fetch_candles
        
        interval_label = TIMEFRAME_TO_INTERVAL.get(timeframe)
        if not interval_label:
            return []
        
        # Calculate date range based on timeframe
        now = datetime.now()
        if timeframe == "daily":
            from_dt = now - timedelta(days=limit + 10)
        elif timeframe == "1h":
            from_dt = now - timedelta(hours=limit * 2)
        elif timeframe == "15m":
            from_dt = now - timedelta(hours=limit)
        elif timeframe == "5m":
            from_dt = now - timedelta(hours=limit // 2 + 1)
        else:  # 1m
            from_dt = now - timedelta(minutes=limit * 2)
        
        candles = fetch_candles(symbol, interval_label, from_dt, now)
        
        # Convert to response format
        result = []
        for c in candles[-limit:]:
            candle_dict = {
                "symbol": symbol,
                "open": c["open"],
                "high": c["high"],
                "low": c["low"],
                "close": c["close"],
                "volume": c["volume"],
            }
            if timeframe == "daily":
                candle_dict["date"] = c["date"].date() if isinstance(c["date"], datetime) else c["date"]
            else:
                candle_dict["timestamp"] = c["date"]
            result.append(candle_dict)
        
        return result
    except Exception as e:
        logger.warning("Failed to fetch live candles for %s: %s", symbol, e)
        return []


@router.get("/{timeframe}/{symbol}")
def get_candles(
    timeframe: str,
    symbol: str,
    limit: int = 50,
    live: Optional[bool] = Query(None, description="Force live data fetch (None=auto based on market hours)"),
    db: Session = Depends(get_db)
):
    """
    Get candles for a symbol at a specific timeframe.
    
    When market is open (9:15-15:30 IST, Mon-Fri), fetches live data from broker.
    When market is closed, returns data from database.
    
    Args:
        timeframe: One of 1m, 5m, 15m, 1h, daily
        symbol: Stock symbol (e.g., NIFTY, SBIN)
        limit: Number of candles to return (default: 50)
        live: Force live fetch (True), force DB (False), or auto (None)
    """
    if timeframe not in TIMEFRAME_MODELS:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid timeframe. Choose from: {', '.join(TIMEFRAME_MODELS.keys())}"
        )
    
    # Determine if we should fetch live data
    use_live = live if live is not None else _is_market_open()
    
    if use_live and timeframe != "daily":  # Daily candles don't need live fetch
        live_candles = _fetch_live_candles(symbol, timeframe, limit)
        if live_candles:
            return {"candles": live_candles, "source": "live", "market_open": True}
    
    # Fallback to database
    model = TIMEFRAME_MODELS[timeframe]
    
    if timeframe == "daily":
        candles = (
            db.query(model)
            .filter(model.symbol == symbol)
            .order_by(model.date.desc())
            .limit(limit)
            .all()
        )
    else:
        candles = (
            db.query(model)
            .filter(model.symbol == symbol)
            .order_by(model.timestamp.desc())
            .limit(limit)
            .all()
        )
    
    # Convert to dict for consistent response
    result = []
    for c in candles:
        candle_dict = {
            "symbol": c.symbol,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume,
        }
        if timeframe == "daily":
            candle_dict["date"] = c.date
        else:
            candle_dict["timestamp"] = c.timestamp
        result.append(candle_dict)
    
    return {"candles": result, "source": "database", "market_open": _is_market_open()}


@router.get("/15m/{symbol}")
def get_candles_15m(symbol: str, live: Optional[bool] = None, db: Session = Depends(get_db)):
    """Legacy endpoint for 15m candles"""
    return get_candles("15m", symbol, 50, live, db)


@router.get("/status")
def get_market_status():
    """Get current market status and data source info."""
    is_open = _is_market_open()
    now = _now_ist()
    return {
        "market_open": is_open,
        "current_time_ist": now.strftime("%Y-%m-%d %H:%M:%S"),
        "market_hours": "09:15 - 15:30 IST",
        "data_source": "live" if is_open else "database",
        "weekday": now.strftime("%A"),
    }
