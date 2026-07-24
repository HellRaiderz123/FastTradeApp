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
    x: pd.DataFrame, y: pd.Series, test_ratio: float = 0.2, val_ratio: float = 0.1
) -> Tuple:
    """
    Per-symbol chronological split: train=70% / val=10% / test=20%.
    Each symbol is split independently so no single market regime dominates.
    The symbol column is dropped before returning.
    """
    train_idx, val_idx, test_idx = [], [], []

    sym_col = "symbol" if "symbol" in x.columns else None

    if sym_col is None:
        n = len(x)
        t_cut = int(n * (1 - test_ratio - val_ratio))
        v_cut = int(n * (1 - test_ratio))
        return (
            x.iloc[:t_cut], x.iloc[t_cut:v_cut], x.iloc[v_cut:],
            y.iloc[:t_cut], y.iloc[t_cut:v_cut], y.iloc[v_cut:],
        )

    for sym, grp in x.groupby(sym_col, sort=False):
        idx = grp.index.tolist()   # already chronological per symbol
        n   = len(idx)
        t_cut = int(n * (1 - test_ratio - val_ratio))
        v_cut = int(n * (1 - test_ratio))
        train_idx.extend(idx[:t_cut])
        val_idx.extend(idx[t_cut:v_cut])
        test_idx.extend(idx[v_cut:])

    drop = [sym_col]
    return (
        x.loc[train_idx].drop(columns=drop),
        x.loc[val_idx].drop(columns=drop),
        x.loc[test_idx].drop(columns=drop),
        y.loc[train_idx],
        y.loc[val_idx],
        y.loc[test_idx],
    )


def _find_best_threshold(y_true: np.ndarray, y_proba: np.ndarray) -> float:
    """Find threshold that maximises geometric-mean of precision & recall on val set.
    Rejects thresholds predicting <20% or >70% as UP (tighter guard against recall bias).
    Falls back to 0.5 if no valid threshold found.
    """
    from sklearn.metrics import precision_score as _p, recall_score as _r
    n = len(y_true)
    best_t, best_score = 0.5, 0.0
    for t in np.arange(0.30, 0.75, 0.01):
        preds = (y_proba >= t).astype(int)
        pred_rate = preds.sum() / n
        # Guard: reject if predicting <10% or >80% as BUY
        if pred_rate < 0.10 or pred_rate > 0.80:
            continue
        p = _p(y_true, preds, zero_division=0)
        r = _r(y_true, preds, zero_division=0)
        # Geometric mean penalises imbalance between precision and recall
        score = (p * r) ** 0.5 if p > 0 and r > 0 else 0.0
        if score > best_score:
            best_score, best_t = score, t
    return round(float(best_t), 2)


def train_stock_model(db: Session, symbols: List[str], config: StockMLConfig) -> Dict[str, float]:
    x, y = build_stock_ml_dataset(db, symbols, config)
    if x.empty or len(x) < config.min_rows:
        raise ValueError(f"Not enough data to train the stock ML model (got {len(x)} rows, need {config.min_rows})")

    class_counts = y.value_counts()
    logger.info(f"📊 Dataset: {len(x)} samples, Classes: {dict(class_counts)}")

    x_train, x_val, x_test, y_train, y_val, y_test = _per_symbol_split(x, y)

    # Undersample majority class in training set only to remove directional bias.
    # Sort by index to preserve chronological order within each symbol.
    train_df = x_train.copy()
    train_df["__label__"] = y_train.values
    minority_n = train_df["__label__"].value_counts().min()
    train_balanced = pd.concat([
        train_df[train_df["__label__"] == cls]
        .sample(minority_n, random_state=42)
        .sort_index()          # restore chronological order
        for cls in [0, 1]
    ]).sort_index()            # interleave both classes chronologically
    x_train = train_balanced.drop(columns=["__label__"])
    y_train = train_balanced["__label__"]
    logger.info(f"📊 Balanced train: {len(x_train)} rows (UP={minority_n} DOWN={minority_n})")

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

    # Calibrate threshold on val set (never seen during training)
    y_val_proba = pipeline.predict_proba(x_val)[:, 1] if len(x_val) else np.array([])
    best_threshold = _find_best_threshold(y_val.values, y_val_proba) if len(x_val) else 0.5
    logger.info(f"📊 Calibrated threshold (val): {best_threshold}")

    # Evaluate on held-out test set using calibrated threshold
    y_proba = pipeline.predict_proba(x_test)[:, 1] if len(x_test) else np.array([])
    y_pred = (y_proba >= best_threshold).astype(int) if len(x_test) else np.array([])
    
    # All metrics computed from calibrated y_pred on held-out test set
    accuracy = float((y_pred == y_test.values).mean()) if len(x_test) else 0.0
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
        "val_rows": int(len(x_val)),
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
