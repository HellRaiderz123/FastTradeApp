from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from sklearn.ensemble import HistGradientBoostingClassifier
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
from app.core.ml.overfitting import check_overfitting

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
    """Find threshold that maximises F1 on val set.
    Pred rate must be 15-55% (not degenerate).
    Prefers higher precision by breaking ties with precision.
    Falls back to 0.45 if no valid threshold found.
    """
    from sklearn.metrics import precision_score as _p, recall_score as _r, f1_score as _f1
    n = len(y_true)
    best_t, best_f1, best_p = 0.45, 0.0, 0.0
    for t in np.arange(0.30, 0.75, 0.01):
        preds = (y_proba >= t).astype(int)
        pred_rate = preds.sum() / n
        if pred_rate < 0.15 or pred_rate > 0.55:
            continue
        p = _p(y_true, preds, zero_division=0)
        r = _r(y_true, preds, zero_division=0)
        f1 = _f1(y_true, preds, zero_division=0)
        # Among equal F1, prefer higher precision (fewer false BUYs)
        if f1 > best_f1 or (f1 == best_f1 and p > best_p):
            best_f1, best_p, best_t = f1, p, t
    return round(float(best_t), 2)


def train_stock_model(db: Session, symbols: List[str], config: StockMLConfig) -> Dict[str, float]:
    x, y = build_stock_ml_dataset(db, symbols, config)
    if x.empty or len(x) < config.min_rows:
        raise ValueError(f"Not enough data to train the stock ML model (got {len(x)} rows, need {config.min_rows})")

    class_counts = y.value_counts()
    logger.info(f"📊 Dataset: {len(x)} samples, Classes: {dict(class_counts)}")

    x_train, x_val, x_test, y_train, y_val, y_test = _per_symbol_split(x, y)

    # Calculate class weights for imbalanced data
    n_samples = len(y_train)
    n_pos = y_train.sum()
    n_neg = n_samples - n_pos
    logger.info(f"📊 Class balance - UP: {n_pos}, DOWN: {n_neg}")

    # Use HistGradientBoostingClassifier - faster, handles NaN, better generalization
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", HistGradientBoostingClassifier(
            max_iter=300,
            max_depth=4,
            learning_rate=0.05,
            min_samples_leaf=30,
            max_leaf_nodes=31,
            l2_regularization=2.0,
            early_stopping=True,
            validation_fraction=0.15,
            n_iter_no_change=20,
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

    # Feature importance from HistGradientBoosting
    try:
        feature_importance = dict(zip(FEATURE_COLUMNS, pipeline.named_steps["clf"].feature_importances_.tolist()))
        top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:10]
        logger.info(f"📊 Top 10 features: {top_features}")
    except Exception:
        feature_importance = {}

    # Train accuracy for overfitting check
    y_train_proba = pipeline.predict_proba(x_train)[:, 1]
    y_train_pred = (y_train_proba >= best_threshold).astype(int)
    train_accuracy = float((y_train_pred == y_train.values).mean())

    # Overfitting diagnostics
    overfit_report = check_overfitting(
        train_accuracy=train_accuracy,
        test_accuracy=accuracy,
        test_precision=precision,
        test_recall=recall,
        test_f1=f1,
        test_roc_auc=roc_auc,
        y_test=y_test.values,
        y_pred=y_pred,
    )
    logger.info(f"🔍 GBM verdict: {overfit_report['verdict']} (score={overfit_report['usability_score']})")

    logger.info(f"✅ Model trained: accuracy={accuracy:.4f}, precision={precision:.4f}, recall={recall:.4f}, f1={f1:.4f}, roc_auc={roc_auc:.4f}")

    metadata = {
        "model_type": "HistGradientBoosting",
        "timeframe": config.timeframe,
        "horizon": config.horizon,
        "return_threshold": config.return_threshold,
        "decision_threshold": best_threshold,
        "train_rows": int(len(x_train)),
        "val_rows": int(len(x_val)),
        "test_rows": int(len(x_test)),
        "total_samples": int(len(x)),
        "train_accuracy": round(train_accuracy, 4),
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
        "overfitting": overfit_report,
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
