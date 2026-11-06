from app.core.ml.config import StockMLConfig
from app.core.ml.stock_model import predict_stock_signal


def ml_stock_signal(db, symbol: str, timeframe=None, use_ensemble: bool = True):
    """Get ML signal — returns NO_TRADE immediately if ML is disabled."""
    import os
    if os.getenv("ML_ENABLED", "true").lower() == "false":
        return {"signal": "NO_TRADE", "confidence": 0, "reason": "ML disabled", "bias": "NEUTRAL", "model_type": "none"}

    config = StockMLConfig(timeframe=timeframe or StockMLConfig().timeframe)

    if use_ensemble:
        try:
            from app.core.ml.ensemble import load_ensemble, predict_ensemble
            ensemble = load_ensemble(config)
            if ensemble is not None:
                result = predict_ensemble(db, symbol, config)
                result["model_type"] = "ensemble"
                return result
        except Exception:
            pass

    try:
        result = predict_stock_signal(db, symbol, config)
        result["model_type"] = "single"
        return result
    except Exception as e:
        return {"signal": "NO_TRADE", "confidence": 0, "reason": f"Prediction error: {e}", "bias": "NEUTRAL", "model_type": "none"}


def ml_signal(symbol: str):
    """Default ML signal for compatibility with existing callers."""
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        return ml_stock_signal(db, symbol)
    finally:
        db.close()
