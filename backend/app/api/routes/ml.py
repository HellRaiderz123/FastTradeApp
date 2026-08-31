"""
ML Model Management API Routes
Endpoints for training, metrics, backfill, and managing ML models
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any

from app.core.ml.config import StockMLConfig
from app.core.ml.model_registry import load_model
from app.core.ml.stock_model import train_stock_model
from app.db.session import SessionLocal
from app.db.models_candles import CandleDaily
from app.core.market.candles import fetch_daily_candles

# LSTM imports (optional - requires tensorflow)
try:
    from app.core.ml.lstm_model import train_lstm_model, predict_lstm_signal, load_lstm_model, TF_AVAILABLE
except ImportError:
    TF_AVAILABLE = False

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ml", tags=["ML"])

ML_CONFIG = StockMLConfig()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_all_symbols(db: Session) -> list:
    """Get all unique symbols from the database"""
    try:
        symbols = db.query(CandleDaily.symbol).distinct().all()
        return [s[0] for s in symbols] if symbols else []
    except Exception:
        return []


def _get_nifty100_symbols(db: Session) -> list:
    """
    Get NIFTY100 symbols from database with sufficient data (500+ days minimum).
    Allows more symbols into training for better model generalization.
    Targets ~100 symbols but accepts anything with 500+ days (2+ years).
    """
    try:
        from sqlalchemy import func
        
        # Query: Get symbols with 500+ daily candles (2+ years of data)
        # This gives better coverage than 1200+ days
        query = db.query(CandleDaily.symbol, func.count(CandleDaily.id).label('count')).group_by(
            CandleDaily.symbol
        ).having(func.count(CandleDaily.id) >= 500).order_by(
            func.count(CandleDaily.id).desc()
        ).limit(200)  # Get up to 200 symbols
        
        symbols = [row[0] for row in query.all()]
        
        if symbols:
            return symbols
        
        # Fallback: Get all symbols if 500 days not available yet
        all_symbols = _get_all_symbols(db)
        return all_symbols[:100] if len(all_symbols) > 100 else all_symbols
        
    except Exception as e:
        # Fallback to all symbols if error
        return _get_all_symbols(db)


@router.get("/metrics")
async def get_ml_metrics(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get ML model metrics including accuracy, precision, recall, F1 score.
    Reports 'ready' if either single or ensemble model file exists.
    """
    try:
        single_meta_path = ML_CONFIG.model_path.with_suffix(".json")
        ensemble_meta_path = ML_CONFIG.model_dir / "ensemble_model.json"

        # Try ensemble first, then single
        if ensemble_meta_path.exists():
            with open(ensemble_meta_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            return {
                "accuracy": metadata.get("accuracy"),
                "precision": metadata.get("precision"),
                "recall": metadata.get("recall"),
                "f1_score": metadata.get("f1_score"),
                "training_date": metadata.get("training_date"),
                "total_samples": metadata.get("total_samples", 0),
                "model_status": "ready",
                "model_type": "ensemble",
                "last_training_duration": metadata.get("training_duration"),
            }

        if single_meta_path.exists():
            with open(single_meta_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            return {
                "accuracy": metadata.get("accuracy"),
                "precision": metadata.get("precision"),
                "recall": metadata.get("recall"),
                "f1_score": metadata.get("f1_score"),
                "training_date": metadata.get("training_date"),
                "total_samples": metadata.get("total_samples", metadata.get("train_rows", 0) + metadata.get("test_rows", 0)),
                "model_status": "ready",
                "model_type": "single",
                "last_training_duration": metadata.get("training_duration"),
                "train_rows": metadata.get("train_rows"),
                "test_rows": metadata.get("test_rows"),
            }
        
        return {
            "accuracy": None,
            "precision": None,
            "recall": None,
            "f1_score": None,
            "training_date": None,
            "total_samples": 0,
            "model_status": "not_trained",
            "model_type": "none",
            "last_training_duration": None,
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading metrics: {str(e)}")


@router.post("/train")
async def train_model_endpoint(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Manually trigger ML model training (runs in background, returns job_id).
    Poll GET /ml/jobs/{job_id} for status and results.
    """
    from app.core.ml.job_store import submit_job, get_running_by_type

    # Prevent duplicate concurrent training jobs
    running = get_running_by_type("train")
    if running:
        return {
            "status": "already_running",
            "job_id": running["job_id"],
            "message": "Training already in progress",
        }

    symbols = _get_nifty100_symbols(db)
    if not symbols:
        raise HTTPException(status_code=400, detail="No stock data found with sufficient history (500+ days)")

    def _run_training():
        local_db = SessionLocal()
        start = datetime.now()
        try:
            result = train_stock_model(local_db, symbols=symbols, config=ML_CONFIG)
            result["training_duration"] = (datetime.now() - start).total_seconds()
            result["symbols_used"] = len(symbols)
            result["symbols_list"] = symbols[:10]
            result["status"] = "success"
            return result
        finally:
            local_db.close()

    job_id = submit_job("train", _run_training, {"symbols_count": len(symbols)})
    return {
        "status": "started",
        "job_id": job_id,
        "message": f"Training started for {len(symbols)} symbols. Poll /ml/jobs/{job_id} for results.",
        "symbols_count": len(symbols),
    }


# --- Backfill status tracking ---
_backfill_status = {
    "running": False,
    "progress": 0,
    "total": 0,
    "current_symbol": "",
    "completed": [],
    "failed": [],
    "message": "idle",
}


def _run_backfill(symbols: list, days: int):
    """Background task: fetch daily candles for all NIFTY100 symbols."""
    global _backfill_status
    _backfill_status["running"] = True
    _backfill_status["total"] = len(symbols)
    _backfill_status["progress"] = 0
    _backfill_status["completed"] = []
    _backfill_status["failed"] = []
    _backfill_status["message"] = "Backfilling daily candles..."

    db = SessionLocal()
    try:
        for i, symbol in enumerate(symbols):
            _backfill_status["current_symbol"] = symbol
            _backfill_status["progress"] = i
            _backfill_status["message"] = f"Fetching {symbol} ({i+1}/{len(symbols)})"
            
            try:
                fetch_daily_candles(db, symbol, days=days)
                _backfill_status["completed"].append(symbol)
                logger.info(f"✅ Backfilled {symbol} ({i+1}/{len(symbols)})")
            except Exception as e:
                _backfill_status["failed"].append({"symbol": symbol, "error": str(e)})
                logger.warning(f"⚠️ Failed {symbol}: {e}")
            
            # Rate limit: Zerodha allows ~3 requests/sec for historical data
            time.sleep(0.4)
        
        _backfill_status["progress"] = len(symbols)
        _backfill_status["message"] = f"Backfill complete: {len(_backfill_status['completed'])} succeeded, {len(_backfill_status['failed'])} failed"
    except Exception as e:
        _backfill_status["message"] = f"Backfill error: {str(e)}"
        logger.exception("❌ Backfill failed")
    finally:
        _backfill_status["running"] = False
        _backfill_status["current_symbol"] = ""
        db.close()


@router.post("/backfill")
async def backfill_daily_candles(background_tasks: BackgroundTasks):
    """
    Backfill daily candle data for all NIFTY100 symbols (runs in background).
    Fetches 900 days of daily data per symbol from Zerodha.
    """
    if _backfill_status["running"]:
        return {
            "status": "already_running",
            "message": _backfill_status["message"],
            "progress": _backfill_status["progress"],
            "total": _backfill_status["total"],
        }
    
    # Get NIFTY100 symbols from scheduler
    from app.core.market.scheduler import _get_daily_symbols
    symbols = _get_daily_symbols()
    
    background_tasks.add_task(_run_backfill, symbols, 2000)
    
    return {
        "status": "started",
        "message": f"Backfilling {len(symbols)} NIFTY100 symbols with 2000 days of daily data",
        "total_symbols": len(symbols),
    }


@router.get("/backfill-status")
async def get_backfill_status():
    """Get the current status of the backfill operation."""
    return {
        "running": _backfill_status["running"],
        "progress": _backfill_status["progress"],
        "total": _backfill_status["total"],
        "current_symbol": _backfill_status["current_symbol"],
        "completed_count": len(_backfill_status["completed"]),
        "failed_count": len(_backfill_status["failed"]),
        "failed_symbols": _backfill_status["failed"][:10],  # First 10 failures
        "message": _backfill_status["message"],
    }


@router.get("/data-summary")
async def get_data_summary():
    """Get summary of available daily candle data for ML training."""
    db = SessionLocal()
    try:
        from sqlalchemy import func
        results = db.query(
            CandleDaily.symbol, 
            func.count(CandleDaily.id).label('count'),
            func.min(CandleDaily.date).label('earliest'),
            func.max(CandleDaily.date).label('latest'),
        ).group_by(CandleDaily.symbol).order_by(func.count(CandleDaily.id).desc()).all()
        
        symbols_data = []
        for sym, cnt, earliest, latest in results:
            symbols_data.append({
                "symbol": sym,
                "candle_count": cnt,
                "earliest_date": str(earliest),
                "latest_date": str(latest),
            })
        
        total_symbols = len(results)
        total_candles = sum(r[1] for r in results)
        symbols_500plus = sum(1 for r in results if r[1] >= 500)
        
        return {
            "total_symbols": total_symbols,
            "total_candles": total_candles,
            "symbols_with_500plus_days": symbols_500plus,
            "symbols": symbols_data,
        }
    finally:
        db.close()


@router.post("/train-stock/{symbol}")
async def train_stock_model_endpoint(symbol: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Train ML model for a specific stock symbol
    """
    try:
        start_time = datetime.now()
        
        # Train the model for specific stock
        result = train_stock_model(db, symbols=[symbol.upper()], config=ML_CONFIG)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        return {
            "status": "success",
            "symbol": symbol,
            "message": f"Model training completed for {symbol}",
            "accuracy": result.get("accuracy"),
            "precision": result.get("precision"),
            "recall": result.get("recall"),
            "f1_score": result.get("f1_score"),
            "total_samples": result.get("total_samples"),
            "training_duration": duration,
            "training_timestamp": start_time.isoformat(),
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Training failed for {symbol}: {str(e)}")


@router.get("/model-info")
async def get_model_info() -> Dict[str, Any]:
    """
    Get general information about the ML model
    """
    try:
        meta_path = ML_CONFIG.model_path.with_suffix(".json")
        
        if not meta_path.exists():
            return {
                "model_type": "GradientBoosting",
                "total_features": 27,
                "feature_names": [
                    "ret_1", "ret_short", "ret_long", "volatility", "atr_norm",
                    "rsi", "macd_hist", "adx",
                    "ema_fast_slope", "ema_slow_slope",
                    "price_vs_ema_fast", "price_vs_ema_slow", "ema_cross",
                    "bb_width", "bb_position",
                    "volume_ratio", "obv_slope",
                    "body_ratio", "upper_shadow", "lower_shadow",
                    "rsi_slope", "ret_5_vs_vol", "close_vs_high20", "close_vs_low20",
                ],
                "model_status": "not_trained",
                "training_date": None,
                "market_condition": "",
            }
        
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        return {
            "model_type": metadata.get("model_type", "GradientBoosting"),
            "total_features": len(metadata.get("feature_columns", [])),
            "feature_names": metadata.get("feature_columns", []),
            "feature_importance": metadata.get("feature_importance", {}),
            "model_status": "ready",
            "training_date": metadata.get("training_date"),
            "market_condition": metadata.get("market_condition", ""),
            "training_duration": metadata.get("training_duration"),
            "dataset_info": metadata.get("dataset_info", {}),
            "symbols_count": metadata.get("symbols_count", 0),
            "class_distribution": metadata.get("class_distribution", {}),
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading model info: {str(e)}")


@router.get("/performance")
async def get_model_performance() -> Dict[str, Any]:
    """
    Get detailed performance metrics for the ML model
    """
    try:
        meta_path = ML_CONFIG.model_path.with_suffix(".json")
        
        if not meta_path.exists():
            return {
                "performance": None,
                "confusion_matrix": None,
                "classification_report": None,
                "model_status": "not_trained",
            }
        
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        return {
            "accuracy": metadata.get("accuracy"),
            "precision": metadata.get("precision"),
            "recall": metadata.get("recall"),
            "f1_score": metadata.get("f1_score"),
            "roc_auc": metadata.get("roc_auc"),
            "confusion_matrix": metadata.get("confusion_matrix"),
            "classification_report": metadata.get("classification_report"),
            "model_status": "ready",
            "cross_validation_score": metadata.get("cross_validation_score"),
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading performance: {str(e)}")


@router.get("/predict/{symbol}")
async def predict_symbol(symbol: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get ML prediction for a single symbol.
    Returns signal (BULLISH / BEARISH / NO_TRADE), confidence, and bias.
    """
    from app.core.signals.ml_engine import ml_stock_signal
    
    try:
        result = ml_stock_signal(db, symbol.upper())
        return {
            "symbol": symbol.upper(),
            "signal": result.get("signal", "NO_TRADE"),
            "confidence": result.get("confidence", 0),
            "bias": result.get("bias", "NEUTRAL"),
            "reason": result.get("reason", ""),
            "indicators": result.get("indicators", {}),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "symbol": symbol.upper(),
            "signal": "NO_TRADE",
            "confidence": 0,
            "bias": "NEUTRAL",
            "reason": f"Prediction error: {str(e)}",
            "indicators": {},
            "timestamp": datetime.now().isoformat(),
        }


class BulkPredictRequest(BaseModel):
    symbols: list[str]


@router.post("/predict-bulk")
async def predict_bulk(request: BulkPredictRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get ML predictions for multiple symbols at once.
    Uses thread pool to run predictions concurrently instead of sequentially.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from app.core.signals.ml_engine import ml_stock_signal

    symbols = [s.upper() for s in request.symbols[:30]]

    def _predict_one(sym: str) -> tuple:
        local_db = SessionLocal()
        try:
            result = ml_stock_signal(local_db, sym)
            return sym, {
                "signal": result.get("signal", "NO_TRADE"),
                "confidence": result.get("confidence", 0),
                "bias": result.get("bias", "NEUTRAL"),
                "reason": result.get("reason", ""),
                "model_type": result.get("model_type", "none"),
            }
        except Exception as e:
            return sym, {
                "signal": "NO_TRADE",
                "confidence": 0,
                "bias": "NEUTRAL",
                "reason": f"Error: {str(e)}",
            }
        finally:
            local_db.close()

    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=min(len(symbols), 6)) as pool:
        futures = [loop.run_in_executor(pool, _predict_one, sym) for sym in symbols]
        results = await asyncio.gather(*futures)

    predictions = dict(results)

    return {
        "predictions": predictions,
        "count": len(predictions),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/training-history")
async def get_training_history() -> Dict[str, Any]:
    """
    Get training history and logs
    """
    try:
        history_path = ML_CONFIG.model_dir / "training_history.json"
        
        if not history_path.exists():
            return {
                "training_count": 0,
                "history": [],
                "last_training": None,
            }
        
        with open(history_path, "r", encoding="utf-8") as f:
            history = json.load(f)
        
        return {
            "training_count": len(history.get("trainings", [])),
            "history": history.get("trainings", []),
            "last_training": history.get("trainings", [{}])[-1] if history.get("trainings") else None,
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading training history: {str(e)}")


# ===========================================================================
# TIER 3 — ML INTELLIGENCE ENDPOINTS
# ===========================================================================


# ---- #15  Model Ensemble (GBM + RF + XGBoost voting) ----------------------

@router.post("/ensemble/train")
async def train_ensemble_endpoint(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Train 3-model ensemble (GBM + RandomForest + XGBoost soft-voting)."""
    from app.core.ml.ensemble import train_ensemble
    try:
        start = datetime.now()
        symbols = _get_nifty100_symbols(db)
        if not symbols:
            raise ValueError("No symbols with sufficient data")
        result = train_ensemble(db, symbols, ML_CONFIG)
        result["training_duration"] = (datetime.now() - start).total_seconds()
        return {"status": "success", **result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ensemble training failed: {e}")


@router.get("/ensemble/info")
async def get_ensemble_info() -> Dict[str, Any]:
    """Get ensemble model metadata and per-model accuracy."""
    from app.core.ml.ensemble import load_ensemble_metadata
    meta = load_ensemble_metadata(ML_CONFIG)
    if not meta:
        return {"status": "not_trained"}
    return {"status": "ready", **meta}


@router.get("/ensemble/predict/{symbol}")
async def ensemble_predict(symbol: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Predict using the 3-model ensemble."""
    from app.core.ml.ensemble import predict_ensemble
    result = predict_ensemble(db, symbol.upper(), ML_CONFIG)
    result["symbol"] = symbol.upper()
    result["timestamp"] = datetime.now().isoformat()
    return result


class EnsembleBulkRequest(BaseModel):
    symbols: list[str]


@router.post("/ensemble/predict-bulk")
async def ensemble_predict_bulk(request: EnsembleBulkRequest, db: Session = Depends(get_db)):
    """Bulk ensemble predictions (max 30)."""
    from app.core.ml.ensemble import predict_ensemble
    preds = {}
    for sym in request.symbols[:30]:
        s = sym.upper()
        try:
            preds[s] = predict_ensemble(db, s, ML_CONFIG)
        except Exception as exc:
            preds[s] = {"signal": "NO_TRADE", "confidence": 0, "bias": "NEUTRAL", "reason": str(exc)}
    return {"predictions": preds, "count": len(preds), "timestamp": datetime.now().isoformat()}


@router.get("/ensemble/compare/{symbol}")
async def ensemble_vs_single(symbol: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Compare ensemble prediction vs single GBM for a given symbol."""
    sym = symbol.upper().strip()
    # Single model
    try:
        from app.core.ml.stock_model import predict_stock_signal
        single = predict_stock_signal(db, sym, ML_CONFIG)
    except Exception as exc:
        single = {"signal": "ERROR", "confidence": 0, "reason": str(exc), "bias": "NEUTRAL"}

    # Ensemble model
    try:
        from app.core.ml.ensemble import predict_ensemble
        ensemble = predict_ensemble(db, sym, ML_CONFIG)
    except Exception as exc:
        ensemble = {"signal": "ERROR", "confidence": 0, "reason": str(exc), "bias": "NEUTRAL"}

    return {
        "symbol": sym,
        "single_model": single,
        "ensemble_model": ensemble,
        "agreement": single.get("signal") == ensemble.get("signal"),
    }


# ---- #16  Feature Importance (SHAP) Dashboard ----------------------------

@router.get("/shap/global")
async def get_global_shap(
    model_type: str = "single",
    max_samples: int = 300,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Compute global SHAP feature importance across dataset sample."""
    try:
        from app.core.ml.shap_explainer import compute_global_shap
        return compute_global_shap(db, ML_CONFIG, max_samples=max_samples, model_type=model_type)
    except ImportError as e:
        return {"error": f"SHAP library not installed: {e}", "features": []}
    except Exception as e:
        return {"error": f"SHAP computation failed: {e}", "features": []}


@router.get("/shap/symbol/{symbol}")
async def get_symbol_shap(
    symbol: str,
    model_type: str = "single",
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """SHAP waterfall for a single symbol's latest prediction."""
    try:
        from app.core.ml.shap_explainer import compute_symbol_shap
        result = compute_symbol_shap(db, symbol.upper(), ML_CONFIG, model_type=model_type)
        return result
    except ImportError as e:
        return {"error": f"SHAP library not installed: {e}", "waterfall": []}
    except Exception as e:
        import traceback, logging
        logging.getLogger(__name__).error(f"SHAP waterfall error: {traceback.format_exc()}")
        return {"error": f"SHAP computation failed: {e}", "waterfall": []}


# ---- #17  Signal-Level Backtest Engine -----------------------------------

class SignalBacktestRequest(BaseModel):
    symbol: str
    model_type: str = "single"
    horizon: int = 5
    threshold_bullish: float = 0.55
    threshold_bearish: float = 0.45
    start_date: str | None = None
    end_date: str | None = None


@router.post("/signal-backtest")
async def run_signal_backtest_endpoint(
    req: SignalBacktestRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Run signal-level backtest for a single symbol."""
    from app.core.ml.signal_backtest import run_signal_backtest
    try:
        return run_signal_backtest(
            db, req.symbol.upper(), ML_CONFIG,
            model_type=req.model_type,
            threshold_bullish=req.threshold_bullish,
            threshold_bearish=req.threshold_bearish,
            horizon=req.horizon,
            start_date=req.start_date,
            end_date=req.end_date,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signal backtest failed: {e}")


class MultiSignalBacktestRequest(BaseModel):
    symbols: list[str]
    model_type: str = "single"
    horizon: int = 5


@router.post("/signal-backtest/multi")
async def run_multi_signal_backtest(
    req: MultiSignalBacktestRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Run signal backtest across multiple symbols."""
    from app.core.ml.signal_backtest import run_multi_symbol_signal_backtest
    try:
        return run_multi_symbol_signal_backtest(
            db, [s.upper() for s in req.symbols[:20]], ML_CONFIG,
            model_type=req.model_type, horizon=req.horizon,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Multi signal backtest failed: {e}")


# ---- #18  News Sentiment in Signal Context --------------------------------

@router.get("/signal-with-news/{symbol}")
async def signal_with_news(
    symbol: str,
    model_type: str = "single",
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get ML signal enriched with news sentiment scoring."""
    from app.core.ml.news_sentiment import get_signal_with_news
    try:
        return get_signal_with_news(db, symbol.upper(), ML_CONFIG, model_type=model_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signal+news failed: {e}")


class NewsSentimentRequest(BaseModel):
    headlines: list[str]


@router.post("/news-sentiment/score")
async def score_news_sentiment(req: NewsSentimentRequest) -> Dict[str, Any]:
    """Score a list of news headlines for sentiment."""
    from app.core.ml.news_sentiment import score_headlines, aggregate_sentiment
    scored = score_headlines(req.headlines)
    agg = aggregate_sentiment(scored)
    return {"headlines": scored, "aggregate": agg}


# ---- #19  Position Correlation Matrix ------------------------------------

class CorrelationRequest(BaseModel):
    symbols: list[str]
    days: int = 90
    method: str = "pearson"


@router.post("/correlation/matrix")
async def get_correlation_matrix(
    req: CorrelationRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Compute pairwise correlation matrix from daily returns."""
    from app.core.ml.correlation import compute_correlation_matrix
    try:
        return compute_correlation_matrix(
            db, [s.upper() for s in req.symbols], days=req.days, method=req.method,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Correlation failed: {e}")


class RollingCorrelationRequest(BaseModel):
    symbol_a: str
    symbol_b: str
    days: int = 252
    window: int = 30


@router.post("/correlation/rolling")
async def get_rolling_correlation(
    req: RollingCorrelationRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Rolling correlation between two symbols over time."""
    from app.core.ml.correlation import compute_rolling_correlation
    try:
        return compute_rolling_correlation(
            db, req.symbol_a.upper(), req.symbol_b.upper(),
            days=req.days, window=req.window,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rolling correlation failed: {e}")


class PortfolioRiskRequest(BaseModel):
    positions: list[dict]
    days: int = 90


@router.post("/correlation/portfolio-risk")
async def get_portfolio_risk(
    req: PortfolioRiskRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Portfolio-level risk analysis (variance, VaR, component risk)."""
    from app.core.ml.correlation import compute_portfolio_risk
    try:
        return compute_portfolio_risk(db, req.positions, days=req.days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Portfolio risk failed: {e}")


# ---- #20  Walk-Forward Optimization --------------------------------------

class WalkForwardRequest(BaseModel):
    model_name: str = "gbm"
    min_train: int = 500
    test_size: int = 100
    step: int = 100
    optimize: bool = False
    optuna_trials: int = 15


@router.post("/walk-forward")
async def run_walk_forward_endpoint(
    req: WalkForwardRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Run walk-forward cross-validation with optional Optuna tuning."""
    from app.core.ml.walk_forward import run_walk_forward
    try:
        symbols = _get_nifty100_symbols(db)
        if not symbols:
            raise ValueError("No symbols with sufficient data")
        return run_walk_forward(
            db, symbols, ML_CONFIG,
            min_train=req.min_train,
            test_size=req.test_size,
            step=req.step,
            model_name=req.model_name,
            optimize=req.optimize,
            optuna_trials=req.optuna_trials,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Walk-forward failed: {e}")


# ---- Background Job Endpoints (async backtest / walk-forward) -------------

@router.post("/signal-backtest/async")
async def start_signal_backtest_async(
    req: SignalBacktestRequest,
) -> Dict[str, Any]:
    """Start signal backtest in a background thread. Returns job_id immediately."""
    from app.core.ml.job_store import submit_job

    def _run_backtest():
        from app.core.ml.signal_backtest import run_signal_backtest
        db = SessionLocal()
        try:
            return run_signal_backtest(
                db, req.symbol.upper(), ML_CONFIG,
                model_type=req.model_type,
                threshold_bullish=req.threshold_bullish,
                threshold_bearish=req.threshold_bearish,
                horizon=req.horizon,
                start_date=req.start_date,
                end_date=req.end_date,
            )
        finally:
            db.close()

    params = {"symbol": req.symbol.upper(), "model_type": req.model_type, "horizon": req.horizon}
    job_id = submit_job("signal-backtest", _run_backtest, params)
    return {"job_id": job_id, "status": "pending", "job_type": "signal-backtest"}


@router.post("/walk-forward/async")
async def start_walk_forward_async(
    req: WalkForwardRequest,
) -> Dict[str, Any]:
    """Start walk-forward in a background thread. Returns job_id immediately."""
    from app.core.ml.job_store import submit_job

    def _run_wf():
        from app.core.ml.walk_forward import run_walk_forward
        db = SessionLocal()
        try:
            symbols = _get_nifty100_symbols(db)
            if not symbols:
                raise ValueError("No symbols with sufficient data")
            return run_walk_forward(
                db, symbols, ML_CONFIG,
                min_train=req.min_train,
                test_size=req.test_size,
                step=req.step,
                model_name=req.model_name,
                optimize=req.optimize,
                optuna_trials=req.optuna_trials,
            )
        finally:
            db.close()

    params = {"model_name": req.model_name, "optimize": req.optimize}
    job_id = submit_job("walk-forward", _run_wf, params)
    return {"job_id": job_id, "status": "pending", "job_type": "walk-forward"}


@router.get("/jobs/latest/{job_type}")
async def get_latest_job(job_type: str) -> Dict[str, Any]:
    """Get the latest completed/running job of a given type."""
    from app.core.ml.job_store import get_latest_by_type
    job = get_latest_by_type(job_type)
    if job is None:
        return {"status": "none", "job_type": job_type}
    return job


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str) -> Dict[str, Any]:
    """Check status of a background ML job."""
    from app.core.ml.job_store import get_job
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ===========================================================================
# LSTM MODEL ENDPOINTS
# ===========================================================================

class LSTMTrainRequest(BaseModel):
    seq_length: int = 20
    epochs: int = 50
    batch_size: int = 64


@router.post("/lstm/train")
async def train_lstm_endpoint(
    req: LSTMTrainRequest = LSTMTrainRequest(),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Train LSTM model for stock prediction (runs in background).
    Requires TensorFlow: pip install tensorflow
    """
    if not TF_AVAILABLE:
        raise HTTPException(
            status_code=400, 
            detail="TensorFlow not installed. Run: pip install tensorflow"
        )
    
    from app.core.ml.job_store import submit_job, get_running_by_type
    
    running = get_running_by_type("lstm-train")
    if running:
        return {
            "status": "already_running",
            "job_id": running["job_id"],
            "message": "LSTM training already in progress",
        }
    
    symbols = _get_nifty100_symbols(db)
    if not symbols:
        raise HTTPException(status_code=400, detail="No stock data found")
    
    def _run_lstm_training():
        local_db = SessionLocal()
        start = datetime.now()
        try:
            result = train_lstm_model(
                local_db, symbols, ML_CONFIG,
                seq_length=req.seq_length,
                epochs=req.epochs,
                batch_size=req.batch_size
            )
            result["training_duration"] = (datetime.now() - start).total_seconds()
            result["status"] = "success"
            return result
        finally:
            local_db.close()
    
    job_id = submit_job("lstm-train", _run_lstm_training, {
        "symbols_count": len(symbols),
        "seq_length": req.seq_length,
        "epochs": req.epochs,
    })
    
    return {
        "status": "started",
        "job_id": job_id,
        "message": f"LSTM training started for {len(symbols)} symbols. Poll /ml/jobs/{job_id} for results.",
        "symbols_count": len(symbols),
    }


@router.get("/lstm/info")
async def get_lstm_info() -> Dict[str, Any]:
    """Get LSTM model metadata and metrics."""
    if not TF_AVAILABLE:
        return {"status": "tensorflow_not_installed", "message": "Install with: pip install tensorflow"}
    
    meta_path = ML_CONFIG.model_dir / "lstm_model.json"
    if not meta_path.exists():
        return {"status": "not_trained"}
    
    with open(meta_path, "r") as f:
        metadata = json.load(f)
    
    return {"status": "ready", **metadata}


@router.get("/lstm/predict/{symbol}")
async def lstm_predict(symbol: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get LSTM prediction for a symbol."""
    if not TF_AVAILABLE:
        raise HTTPException(status_code=400, detail="TensorFlow not installed")
    
    result = predict_lstm_signal(db, symbol.upper(), ML_CONFIG)
    result["symbol"] = symbol.upper()
    result["timestamp"] = datetime.now().isoformat()
    result["model_type"] = "LSTM"
    return result


class LSTMBulkRequest(BaseModel):
    symbols: list[str]


@router.post("/lstm/predict-bulk")
async def lstm_predict_bulk(
    request: LSTMBulkRequest, 
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Bulk LSTM predictions (max 20 symbols)."""
    if not TF_AVAILABLE:
        raise HTTPException(status_code=400, detail="TensorFlow not installed")
    
    predictions = {}
    for sym in request.symbols[:20]:
        s = sym.upper()
        try:
            predictions[s] = predict_lstm_signal(db, s, ML_CONFIG)
        except Exception as e:
            predictions[s] = {
                "signal": "NO_TRADE", 
                "confidence": 0, 
                "bias": "NEUTRAL", 
                "reason": str(e)
            }
    
    return {
        "predictions": predictions,
        "count": len(predictions),
        "model_type": "LSTM",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/lstm/compare/{symbol}")
async def lstm_vs_gbm(symbol: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Compare LSTM vs GradientBoosting predictions for a symbol."""
    sym = symbol.upper()
    
    # GBM prediction
    try:
        from app.core.ml.stock_model import predict_stock_signal
        gbm = predict_stock_signal(db, sym, ML_CONFIG)
        gbm["model"] = "HistGradientBoosting"
    except Exception as e:
        gbm = {"signal": "ERROR", "confidence": 0, "reason": str(e), "bias": "NEUTRAL"}
    
    # LSTM prediction
    if TF_AVAILABLE:
        try:
            lstm = predict_lstm_signal(db, sym, ML_CONFIG)
            lstm["model"] = "LSTM"
        except Exception as e:
            lstm = {"signal": "ERROR", "confidence": 0, "reason": str(e), "bias": "NEUTRAL"}
    else:
        lstm = {"signal": "N/A", "confidence": 0, "reason": "TensorFlow not installed", "bias": "NEUTRAL"}
    
    return {
        "symbol": sym,
        "gbm_model": gbm,
        "lstm_model": lstm,
        "agreement": gbm.get("signal") == lstm.get("signal"),
        "timestamp": datetime.now().isoformat(),
    }

