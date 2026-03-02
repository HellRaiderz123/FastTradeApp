from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models_candles import Candle1m, Candle5m, Candle15m, Candle1h, CandleDaily

router = APIRouter(prefix="/candles", tags=["Candles"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Timeframe model mapping
TIMEFRAME_MODELS = {
    "1m": Candle1m,
    "5m": Candle5m,
    "15m": Candle15m,
    "1h": Candle1h,
    "daily": CandleDaily
}

@router.get("/{timeframe}/{symbol}")
def get_candles(timeframe: str, symbol: str, limit: int = 50, db: Session = Depends(get_db)):
    """
    Get candles for a symbol at a specific timeframe
    
    Args:
        timeframe: One of 1m, 5m, 15m, 1h, daily
        symbol: Stock symbol (e.g., NIFTY, SBIN)
        limit: Number of candles to return (default: 50)
    """
    if timeframe not in TIMEFRAME_MODELS:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid timeframe. Choose from: {', '.join(TIMEFRAME_MODELS.keys())}"
        )
    
    model = TIMEFRAME_MODELS[timeframe]
    
    if timeframe == "daily":
        # Daily candles use date field instead of timestamp
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
    
    return candles


@router.get("/15m/{symbol}")
def get_candles_15m(symbol: str, db: Session = Depends(get_db)):
    """Legacy endpoint for 15m candles - redirects to new endpoint"""
    return get_candles("15m", symbol, 50, db)
