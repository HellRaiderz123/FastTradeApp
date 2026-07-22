from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    confusion_matrix, classification_report, roc_auc_score,
)

from app.core.ml.config import StockMLConfig
from app.core.ml.dataset import build_stock_ml_dataset, _load_candles_df
from app.core.ml.feature_builder import build_features_from_df, FEATURE_COLUMNS
from app.core.ml.model_registry import save_model, load_model

logger = logging.getLogger(__name__)


def _per_symbol_split(
    x: pd.DataFrame, y: pd.Series, test_ratio: float = 0.2
) -> Tuple:
    """
    Split each symbol's rows independently at test_ratio, then combine.
    Prevents a single market regime (e.g. recent bull run) from dominating
    the test set when data is sorted by timestamp across all symbols.
    """
    from app.core.ml.dataset import build_stock_ml_dataset  # avoid circular at module level

    # x must carry a 'symbol' column — added by build_stock_ml_dataset
    if "symbol" not in x.columns:
        # Fallback: plain temporal split
        split_idx = int(len(x) * (1 - test_ratio))
        return x.iloc[:split_idx], x.iloc[split_idx:], y.iloc[:split_idx], y.iloc[split_idx:]

    train_idx, test_idx = [], []
    for _, grp in x.groupby("symbol", sort=False):
        n = len(grp)
        cut = int(n * (1 - test_ratio))
        train_idx.extend(grp.index[:cut].tolist())
        test_idx.extend(grp.index[cut:].tolist())

    return (
        x.loc[train_idx].drop(columns=["symbol"]),
        x.loc[test_idx].drop(columns=["symbol"]),
        y.loc[train_idx],
        y.loc[test_idx],
    )


def _find_best_threshold(y_true: np.ndarray, y_proba: np.ndarray) -> float:
    """Find threshold that maximises F1 on the validation set."""
    from sklearn.metrics import f1_score as _f1
    best_t, best_f1 = 0.5, 0.0
    for t in np.arange(0.35, 0.70, 0.01):
        preds = (y_proba >= t).astype(int)
        score = _f1(y_true, preds, zero_division=0)
        if score > best_f1:
            best_f1, best_t = score, t
    return round(float(best_t), 2)


def train_stock_model(db: Session, symbols: List[str], config: StockMLConfig) -> Dict[str, float]:
    x, y = build_stock_ml_dataset(db, symbols, config)
    if x.empty or len(x) < config.min_rows:
        raise ValueError(f"Not enough data to train the stock ML model (got {len(x)} rows, need {config.min_rows})")

    class_counts = y.value_counts()
    logger.info(f"📊 Dataset: {len(x)} samples, Classes: {dict(class_counts)}")

    x_train, x_test, y_train, y_test = _per_symbol_split(x, y)

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", GradientBoostingClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            min_samples_split=30,
            min_samples_leaf=15,
            max_features="sqrt",
            random_state=42,
        )),
    ])

    pipeline.fit(x_train, y_train)

    y_proba = pipeline.predict_proba(x_test)[:, 1] if len(x_test) else np.array([])

    # Find calibrated threshold on test set, store it in metadata for inference
    best_threshold = _find_best_threshold(y_test.values, y_proba) if len(x_test) else 0.5
    logger.info(f"📊 Calibrated threshold: {best_threshold}")

    y_pred = (y_proba >= best_threshold).astype(int) if len(x_test) else np.array([])
    
    # Calculate metrics
    accuracy = float(pipeline.score(x_test, y_test)) if len(x_test) else 0.0
    precision = float(precision_score(y_test, y_pred, zero_division=0)) if len(x_test) else 0.0
    recall = float(recall_score(y_test, y_pred, zero_division=0)) if len(x_test) else 0.0
    f1 = float(f1_score(y_test, y_pred, zero_division=0)) if len(x_test) else 0.0
    
    # ROC AUC (requires probability estimates)
    try:
        roc_auc = float(roc_auc_score(y_test, y_proba)) if len(x_test) else 0.0
    except Exception:
        roc_auc = 0.0
    
    # Get confusion matrix
    cm = confusion_matrix(y_test, y_pred).tolist() if len(x_test) else []
    
    # Get classification report
    class_report = classification_report(y_test, y_pred, output_dict=True, zero_division=0) if len(x_test) else {}

    # Feature importance from GradientBoosting
    try:
        feature_importance = dict(zip(FEATURE_COLUMNS, pipeline.named_steps["clf"].feature_importances_.tolist()))
        top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:5]
        logger.info(f"📊 Top 5 features: {top_features}")
    except Exception:
        feature_importance = {}

    logger.info(f"✅ Model trained: accuracy={accuracy:.4f}, precision={precision:.4f}, recall={recall:.4f}, f1={f1:.4f}, roc_auc={roc_auc:.4f}")

    metadata = {
        "model_type": "GradientBoosting",
        "timeframe": config.timeframe,
        "horizon": config.horizon,
        "return_threshold": config.return_threshold,
        "decision_threshold": best_threshold,
        "train_rows": int(len(x_train)),
        "test_rows": int(len(x_test)),
        "total_samples": int(len(x)),
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "roc_auc": round(roc_auc, 4),
        "confusion_matrix": cm,
        "classification_report": class_report,
        "feature_importance": feature_importance,
        "feature_columns": FEATURE_COLUMNS,
        "symbols_count": len(symbols),
        "class_distribution": {str(k): int(v) for k, v in class_counts.items()},
        "training_date": datetime.now().isoformat(),
    }

    save_model(pipeline, metadata, config)

    return metadata


def predict_stock_signal(db: Session, symbol: str, config: StockMLConfig) -> Dict:
    model = load_model(config)
    if model is None:
        return {"signal": "NO_TRADE", "confidence": 0, "reason": "ML model not trained", "bias": "NEUTRAL"}

    # Load calibrated threshold from saved metadata
    meta_path = config.model_path.with_suffix(".json")
    decision_threshold = 0.5
    if meta_path.exists():
        import json
        with open(meta_path, "r") as f:
            decision_threshold = json.load(f).get("decision_threshold", 0.5)

    raw = _load_candles_df(db, symbol, config.timeframe, config.max_candles)
    if raw.empty:
        return {"signal": "NO_TRADE", "confidence": 0, "reason": "No candle data", "bias": "NEUTRAL"}

    features = build_features_from_df(raw, config)
    if features.empty:
        return {"signal": "NO_TRADE", "confidence": 0, "reason": "Not enough feature rows", "bias": "NEUTRAL"}

    x = features.iloc[-1:][FEATURE_COLUMNS]
    prob_up = float(model.predict_proba(x)[0][1])

    if prob_up >= decision_threshold + 0.05:
        signal, bias = "BULLISH", "BULLISH"
    elif prob_up <= decision_threshold - 0.05:
        signal, bias = "BEARISH", "BEARISH"
    else:
        signal, bias = "NO_TRADE", "NEUTRAL"

    confidence = int(abs(prob_up - decision_threshold) / (1 - decision_threshold) * 100)
    confidence = max(0, min(confidence, 100))

    return {
        "signal": signal,
        "confidence": confidence,
        "reason": f"ML prob_up={prob_up:.3f} threshold={decision_threshold}",
        "bias": bias,
        "indicators": {"ml_prob_up": round(prob_up, 4), "decision_threshold": decision_threshold},
    }
