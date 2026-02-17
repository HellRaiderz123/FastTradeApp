"""
ML Model Management API Routes
Endpoints for training, metrics, backfill, and managing ML models
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
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
        ).limit(150)  # Get up to 150 symbols
        
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
    Get ML model metrics including accuracy, precision, recall, F1 score
    """
    try:
        # Check if model exists
        meta_path = ML_CONFIG.model_path.with_suffix(".json")
        
        if not meta_path.exists():
            return {
                "accuracy": None,
                "precision": None,
                "recall": None,
                "f1_score": None,
                "training_date": None,
                "total_samples": 0,
                "model_status": "not_trained",
                "last_training_duration": None,
            }
        
        # Load metadata
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        # Return metrics with defaults for missing fields (from old models)
        return {
            "accuracy": metadata.get("accuracy"),
            "precision": metadata.get("precision"),  # May be None for old models
            "recall": metadata.get("recall"),  # May be None for old models
            "f1_score": metadata.get("f1_score"),  # May be None for old models
            "training_date": metadata.get("training_date"),
            "total_samples": metadata.get("total_samples", metadata.get("train_rows", 0) + metadata.get("test_rows", 0)),
            "model_status": "ready",
            "last_training_duration": metadata.get("training_duration"),
            "train_rows": metadata.get("train_rows"),
            "test_rows": metadata.get("test_rows"),
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading metrics: {str(e)}")


@router.post("/train")
async def train_model_endpoint(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Manually trigger ML model training
    Trains on NIFTY100 symbols with 500+ days of daily candle data for swing trading
    """
    try:
        start_time = datetime.now()
        
        # Get NIFTY100 symbols with 500+ days of data
        symbols = _get_nifty100_symbols(db)
        if not symbols:
            raise ValueError("No stock data found in database with sufficient history (500+ days)")
        
        # Train the model
        result = train_stock_model(db, symbols=symbols, config=ML_CONFIG)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        return {
            "status": "success",
            "message": f"Model training completed successfully using {len(symbols)} NIFTY100 symbols with 500+ days of data",
            "symbols_used": len(symbols),
            "symbols_list": symbols[:10],  # Return first 10 for reference
            "accuracy": result.get("accuracy"),
            "precision": result.get("precision"),
            "recall": result.get("recall"),
            "f1_score": result.get("f1_score"),
            "total_samples": result.get("total_samples"),
            "train_rows": result.get("train_rows"),
            "test_rows": result.get("test_rows"),
            "training_duration": duration,
            "training_timestamp": start_time.isoformat(),
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Training failed: {str(e)}")


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
    
    background_tasks.add_task(_run_backfill, symbols, 900)
    
    return {
        "status": "started",
        "message": f"Backfilling {len(symbols)} NIFTY100 symbols with 900 days of daily data",
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
                "total_features": 24,
                "feature_names": [
                    "ret_1", "ret_short", "ret_long", "volatility", "atr_norm",
                    "rsi", "macd_hist", "adx", "ema_fast", "ema_slow", "ema_long",
                    "ema_fast_slope", "ema_slow_slope", "price_vs_ema_fast",
                    "price_vs_ema_slow", "ema_cross", "bb_width", "bb_position",
                    "volume_ratio", "obv_slope", "body_ratio", "upper_shadow", "lower_shadow",
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
