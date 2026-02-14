from typing import Dict, Optional

from app.db.session import SessionLocal
from app.core.ml.config import StockMLConfig
from app.core.ml.stock_model import predict_stock_signal


def ml_stock_signal(db, symbol: str, timeframe: Optional[str] = None) -> Dict:
    config = StockMLConfig(timeframe=timeframe or StockMLConfig().timeframe)
    if not config.enabled:
        return {
            "signal": "NO_TRADE",
            "confidence": 0,
            "reason": "ML disabled",
            "bias": "NEUTRAL",
        }

    return predict_stock_signal(db, symbol, config)


def ml_signal(symbol: str) -> Dict:
    """Default ML signal for compatibility with existing callers."""
    config = StockMLConfig()
    if not config.enabled:
        return {
            "signal": "NO_TRADE",
            "confidence": 0,
            "reason": "ML disabled",
            "bias": "NEUTRAL",
        }

    db = SessionLocal()
    try:
        return predict_stock_signal(db, symbol, config)
    finally:
        db.close()
