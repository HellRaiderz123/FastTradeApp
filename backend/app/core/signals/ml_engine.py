from typing import Dict, Optional

from app.db.session import SessionLocal
from app.core.ml.config import StockMLConfig
from app.core.ml.stock_model import predict_stock_signal


def ml_stock_signal(db, symbol: str, timeframe: Optional[str] = None, use_ensemble: bool = True) -> Dict:
    """Get ML signal for a symbol.
    
    Tries ensemble first (if available & use_ensemble=True),
    falls back to single GBM. Does NOT require STOCK_ML_ENABLED;
    if a trained model exists on disk, it will be used.
    """
    config = StockMLConfig(timeframe=timeframe or StockMLConfig().timeframe)

    # Try ensemble first
    if use_ensemble:
        try:
            from app.core.ml.ensemble import load_ensemble, predict_ensemble
            ensemble = load_ensemble(config)
            if ensemble is not None:
                result = predict_ensemble(db, symbol, config)
                result["model_type"] = "ensemble"
                return result
        except Exception:
            pass  # fall through to single model

    # Single GBM
    try:
        result = predict_stock_signal(db, symbol, config)
        result["model_type"] = "single"
        return result
    except Exception as e:
        return {
            "signal": "NO_TRADE",
            "confidence": 0,
            "reason": f"Prediction error: {e}",
            "bias": "NEUTRAL",
            "model_type": "none",
        }


def ml_signal(symbol: str) -> Dict:
    """Default ML signal for compatibility with existing callers."""
    db = SessionLocal()
    try:
        return ml_stock_signal(db, symbol)
    finally:
        db.close()
