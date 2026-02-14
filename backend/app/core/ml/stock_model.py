from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

from app.core.ml.config import StockMLConfig
from app.core.ml.dataset import build_stock_ml_dataset, _load_candles_df
from app.core.ml.feature_builder import build_features_from_df, FEATURE_COLUMNS
from app.core.ml.model_registry import save_model, load_model


def _temporal_split(x: pd.DataFrame, y: pd.Series, test_ratio: float = 0.2) -> Tuple:
    split_idx = int(len(x) * (1 - test_ratio))
    x_train, x_test = x.iloc[:split_idx], x.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    return x_train, x_test, y_train, y_test


def train_stock_model(db: Session, symbols: List[str], config: StockMLConfig) -> Dict[str, float]:
    x, y = build_stock_ml_dataset(db, symbols, config)
    if x.empty or len(x) < config.min_rows:
        raise ValueError("Not enough data to train the stock ML model")

    x_train, x_test, y_train, y_test = _temporal_split(x, y)

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=500, class_weight="balanced")),
    ])

    pipeline.fit(x_train, y_train)

    accuracy = float(pipeline.score(x_test, y_test)) if len(x_test) else 0.0

    metadata = {
        "timeframe": config.timeframe,
        "horizon": config.horizon,
        "return_threshold": config.return_threshold,
        "train_rows": int(len(x_train)),
        "test_rows": int(len(x_test)),
        "accuracy": accuracy,
        "feature_columns": FEATURE_COLUMNS,
    }

    save_model(pipeline, metadata, config)

    return metadata


def _prob_to_signal(prob_up: float, config: StockMLConfig) -> Dict[str, str]:
    if prob_up >= config.bullish_prob_threshold:
        return {"signal": "BULLISH", "bias": "BULLISH"}
    if prob_up <= config.bearish_prob_threshold:
        return {"signal": "BEARISH", "bias": "BEARISH"}
    return {"signal": "NO_TRADE", "bias": "NEUTRAL"}


def predict_stock_signal(db: Session, symbol: str, config: StockMLConfig) -> Dict:
    model = load_model(config)
    if model is None:
        return {
            "signal": "NO_TRADE",
            "confidence": 0,
            "reason": "ML model not trained",
            "bias": "NEUTRAL",
        }

    raw = _load_candles_df(db, symbol, config.timeframe, config.max_candles)
    if raw.empty:
        return {
            "signal": "NO_TRADE",
            "confidence": 0,
            "reason": "No candle data",
            "bias": "NEUTRAL",
        }

    features = build_features_from_df(raw, config)
    if features.empty:
        return {
            "signal": "NO_TRADE",
            "confidence": 0,
            "reason": "Not enough feature rows",
            "bias": "NEUTRAL",
        }

    latest = features.iloc[-1:]
    x = latest[FEATURE_COLUMNS]

    prob_up = float(model.predict_proba(x)[0][1])
    signal_map = _prob_to_signal(prob_up, config)
    confidence = int(max(prob_up, 1 - prob_up) * 100)

    return {
        "signal": signal_map["signal"],
        "confidence": confidence,
        "reason": f"ML prob_up={prob_up:.3f}",
        "bias": signal_map["bias"],
        "indicators": {
            "ml_prob_up": round(prob_up, 4),
        },
    }
