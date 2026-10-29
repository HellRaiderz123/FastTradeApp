"""
Historical candle data retrieval for backtesting.
"""
import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional

from app.db.session import SessionLocal
from app.db.models_candles import Candle15m, CandleDaily

logger = logging.getLogger(__name__)

INTERVAL_MODEL_MAP = {
    "15minute": Candle15m,
    "day": CandleDaily,
}


def get_historical_candles(
    symbol: str,
    start_date: date,
    end_date: date,
    interval: str = "15minute",
) -> List[Dict[str, Any]]:
    """Fetch historical candles from DB for backtesting."""
    model = INTERVAL_MODEL_MAP.get(interval)
    if not model:
        logger.warning(f"Unsupported interval: {interval}, falling back to 15m")
        model = Candle15m

    db = SessionLocal()
    try:
        if model == CandleDaily:
            rows = (
                db.query(model)
                .filter(model.symbol == symbol, model.date >= start_date, model.date <= end_date)
                .order_by(model.date)
                .all()
            )
            return [
                {
                    "date": r.date,
                    "open": r.open,
                    "high": r.high,
                    "low": r.low,
                    "close": r.close,
                    "volume": r.volume,
                }
                for r in rows
            ]
        else:
            start_dt = datetime.combine(start_date, datetime.min.time())
            end_dt = datetime.combine(end_date, datetime.max.time())
            rows = (
                db.query(model)
                .filter(model.symbol == symbol, model.timestamp >= start_dt, model.timestamp <= end_dt)
                .order_by(model.timestamp)
                .all()
            )
            return [
                {
                    "date": r.timestamp.date() if r.timestamp else start_date,
                    "timestamp": r.timestamp,
                    "open": r.open,
                    "high": r.high,
                    "low": r.low,
                    "close": r.close,
                    "volume": r.volume,
                }
                for r in rows
            ]
    finally:
        db.close()
