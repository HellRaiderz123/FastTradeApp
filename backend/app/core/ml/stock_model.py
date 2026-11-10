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
    accuracy_score,
)

from app.core.ml.config import StockMLConfig
from app.core.ml.dataset import build_stock_ml_dataset, _load_candles_df
from app.core.ml.feature_builder import build_features_from_df, FEATURE_COLUMNS
from app.core.ml.model_registry import save_model, load_model
from app.core.ml.overfitting import check_overfitting

logger = logging.getLogger(__name__)


def _chronological_split(
    x: pd.DataFrame,
    y: pd.Series,
    test_ratio: float = 0.20,
    val_ratio: float = 0.10,
    embargo_bars: int = 0,
) -> Tuple:
    """
    Global chronological split anchored on the timestamp column.

    All symbols are sorted together by date so the test set is always
    the most recent calendar period — not a random 20% of each symbol.

    embargo_bars rows immediately before each boundary are dropped to
    prevent any residual label-window leakage across splits.

    Returns: x_train, x_val, x_test, y_train, y_val, y_test
    """
    drop_cols = ["symbol"]

    # Use timestamp for ordering if available, else fall back to positional
    if "timestamp" in x.columns:
        order = x["timestamp"].argsort()
        x = x.iloc[order].reset_index(drop=True)
        y = y.iloc[order].reset_index(drop=True)
        drop_cols.append("timestamp")
    
    n = len(x)
    t_cut = int(n * (1 - test_ratio - val_ratio))
    v_cut = int(n * (1 - test_ratio))

    # Embargo: drop `embargo_bars` rows on each side of every boundary
    e = embargo_bars
    train_end   = t_cut - e
    val_start   = t_cut + e
    val_end     = v_cut - e
    test_start  = v_cut + e

    if train_end <= 0 or val_start >= val_end or test_start >= n:
        # Not enough data for embargo — fall back to no embargo
        logger.warning("Embargo too large for dataset size — skipping embargo")
        train_end, val_start, val_end, test_start = t_cut, t_cut, v_cut, v_cut

    existing_drop = [c for c in drop_cols if c in x.columns]

    x_train = x.iloc[:train_end].drop(columns=existing_drop)
    x_val   = x.iloc[val_start:val_end].drop(columns=existing_drop)
    x_test  = x.iloc[test_start:].drop(columns=existing_drop)
    y_train = y.iloc[:train_end]
    y_val   = y.iloc[val_start:val_end]
    y_test  = y.iloc[test_start:]

    logger.info(
        f"Split (global chrono): train={len(x_train)}, val={len(x_val)}, "
        f"test={len(x_test)}, embargo={e} bars each side"
    )
    return x_train, x_val, x_test, y_train, y_val, y_test


def _find_best_threshold(y_true: np.ndarray, y_proba: np.ndarray) -> float:
    """
    Threshold search on val set for the BULLISH class probability.
    Maximises F1 subject to precision >= 40% and pred_rate in [8%, 55%].
    Falls back to best-F1 candidate if no threshold meets the bar.
    """
    n = len(y_true)
    if n < 50:
        return 0.50

    base_rate = float(y_true.mean())
    logger.info(f"Threshold search: val_size={n}, base_rate={base_rate:.3f}, "
                f"proba=[{y_proba.min():.3f}, {y_proba.max():.3f}]")

    candidates = []
    for t in np.arange(0.25, 0.80, 0.01):
        preds     = (y_proba >= t).astype(int)
        pred_rate = preds.mean()
        if pred_rate < 0.08 or pred_rate > 0.55:
            continue
        p = precision_score(y_true, preds, zero_division=0)
        r = recall_score(y_true, preds, zero_division=0)
        f = f1_score(y_true, preds, zero_division=0)
        candidates.append((round(t, 2), p, r, f, pred_rate))

    if not candidates:
        logger.warning("Threshold search: no candidate in pred_rate [8%,55%]. Using 0.50")
        return 0.50

    valid = [(t, p, r, f, pr) for t, p, r, f, pr in candidates if p >= 0.40 and r >= 0.10]
    if valid:
        best = max(valid, key=lambda x: x[3])
        logger.info(f"Threshold: t={best[0]}, prec={best[1]:.3f}, rec={best[2]:.3f}, "
                    f"f1={best[3]:.3f}, pred_rate={best[4]:.3f}")
        return best[0]

    best_f1 = max(candidates, key=lambda x: x[3])
    logger.warning(f"Threshold fallback (best-F1): t={best_f1[0]}, "
                   f"prec={best_f1[1]:.3f}, rec={best_f1[2]:.3f}, f1={best_f1[3]:.3f}")
    return best_f1[0]


def train_stock_model(db: Session, symbols: List[str], config: StockMLConfig) -> Dict:
    x, y = build_stock_ml_dataset(db, symbols, config)
    if x.empty or len(x) < config.min_rows:
        raise ValueError(f"Not enough data ({len(x)} rows, need {config.min_rows})")

    label_counts = y.value_counts().to_dict()
    logger.info(f"Dataset: {len(x)} samples (strided), label dist: {label_counts}")

    # -----------------------------------------------------------------------
    # Convert 3-class labels to binary for GBM:
    # BULLISH=1 → positive class
    # NEUTRAL=0 and BEARISH=-1 → negative class (0)
    # This is semantically correct: we train "is this a clean long setup?"
    # -----------------------------------------------------------------------
    y_binary = (y == 1).astype(int)

    x_train, x_val, x_test, y_train, y_val, y_test = _chronological_split(
        x, y_binary, embargo_bars=config.horizon
    )

    n_pos = int(y_train.sum())
    n_neg = len(y_train) - n_pos
    imbalance = n_neg / max(n_pos, 1)
    logger.info(f"Class balance — BULLISH: {n_pos}, OTHER: {n_neg}, ratio: {imbalance:.1f}x")

    # Cap weight at 3x to avoid over-correction
    pos_weight    = min(imbalance, 3.0) if imbalance > 1.2 else 1.0
    sample_weight = np.where(y_train.values == 1, pos_weight, 1.0).astype(float)

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", HistGradientBoostingClassifier(
            max_iter=500,
            max_depth=4,
            learning_rate=0.05,
            min_samples_leaf=40,
            max_leaf_nodes=31,
            l2_regularization=1.0,
            early_stopping=True,
            validation_fraction=0.15,
            n_iter_no_change=25,
            random_state=42,
        )),
    ])

    pipeline.fit(x_train, y_train, clf__sample_weight=sample_weight)

    # Calibrate threshold on val (never seen during training)
    y_val_proba   = pipeline.predict_proba(x_val)[:, 1] if len(x_val) else np.array([])
    best_threshold = _find_best_threshold(y_val.values, y_val_proba) if len(x_val) else 0.50
    logger.info(f"Calibrated threshold (val): {best_threshold}")

    # Evaluate on held-out test set
    y_proba = pipeline.predict_proba(x_test)[:, 1] if len(x_test) else np.array([])
    y_pred  = (y_proba >= best_threshold).astype(int) if len(x_test) else np.array([])

    accuracy  = float(accuracy_score(y_test, y_pred))         if len(x_test) else 0.0
    precision = float(precision_score(y_test, y_pred, zero_division=0)) if len(x_test) else 0.0
    recall    = float(recall_score(y_test, y_pred, zero_division=0))    if len(x_test) else 0.0
    f1        = float(f1_score(y_test, y_pred, zero_division=0))        if len(x_test) else 0.0
    try:
        roc_auc = float(roc_auc_score(y_test, y_proba)) if len(x_test) else 0.0
    except Exception:
        roc_auc = 0.0

    cm           = confusion_matrix(y_test, y_pred).tolist() if len(x_test) else []
    class_report = classification_report(y_test, y_pred, output_dict=True, zero_division=0) \
                   if len(x_test) else {}

    try:
        feature_importance = dict(zip(
            FEATURE_COLUMNS,
            pipeline.named_steps["clf"].feature_importances_.tolist()
        ))
        top10 = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:10]
        logger.info(f"Top 10 features: {top10}")
    except Exception:
        feature_importance = {}

    y_train_proba = pipeline.predict_proba(x_train)[:, 1]
    y_train_pred  = (y_train_proba >= best_threshold).astype(int)
    train_accuracy = float(accuracy_score(y_train, y_train_pred))

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
    logger.info(f"GBM verdict: {overfit_report['verdict']} (score={overfit_report['usability_score']})")
    logger.info(f"Trained: acc={accuracy:.4f}, prec={precision:.4f}, "
                f"rec={recall:.4f}, f1={f1:.4f}, roc_auc={roc_auc:.4f}")

    metadata = {
        "model_type": "HistGradientBoosting",
        "label_scheme": "triple_barrier_3class_binary_bullish",
        "timeframe": config.timeframe,
        "horizon": config.horizon,
        "tp_atr_mult": config.tp_atr_mult,
        "sl_atr_mult": config.sl_atr_mult,
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
        "label_distribution": {str(k): int(v) for k, v in label_counts.items()},
        "training_date": datetime.now().isoformat(),
        "overfitting": overfit_report,
    }

    save_model(pipeline, metadata, config)
    return metadata


def predict_stock_signal(db: Session, symbol: str, config: StockMLConfig) -> Dict:
    """
    Predict using trained GBM.

    Semantics (correct):
      prob_up >= threshold          → BULLISH  (model confident this is a long setup)
      prob_up <  threshold          → NO_TRADE (model not confident — could be flat or down)

    We do NOT emit BEARISH from a binary model trained on BULLISH vs (NEUTRAL+BEARISH).
    A low prob_up means "not a clean long setup", not "confirmed short."
    """
    try:
        model = load_model(config)
        if model is None:
            return {"signal": "NO_TRADE", "confidence": 0,
                    "reason": "ML model not trained", "bias": "NEUTRAL"}

        import json
        decision_threshold = 0.50
        meta_path = config.model_path.with_suffix(".json")
        if meta_path.exists():
            try:
                with open(meta_path) as f:
                    decision_threshold = json.load(f).get("decision_threshold", 0.50)
            except Exception as e:
                logger.warning(f"Failed to load model metadata: {e}")

        raw = _load_candles_df(db, symbol, config.timeframe, config.max_candles)
        if raw.empty:
            return {"signal": "NO_TRADE", "confidence": 0,
                    "reason": "No candle data", "bias": "NEUTRAL"}

        features = build_features_from_df(raw, config)
        if features.empty:
            return {"signal": "NO_TRADE", "confidence": 0,
                    "reason": "Not enough feature rows", "bias": "NEUTRAL"}

        x = features.iloc[-1:][FEATURE_COLUMNS]
        if x.isnull().any().any():
            x = x.fillna(0)

        prob_up = float(model.predict_proba(x)[0][1])

        if prob_up >= decision_threshold:
            signal, bias = "BULLISH", "BULLISH"
            confidence = int((prob_up - decision_threshold) / (1.0 - decision_threshold) * 100)
        else:
            signal, bias = "NO_TRADE", "NEUTRAL"
            confidence = 0

        confidence = max(0, min(confidence, 100))

        return {
            "signal": signal,
            "confidence": confidence,
            "reason": f"GBM prob_bullish={prob_up:.3f} threshold={decision_threshold:.3f}",
            "bias": bias,
            "indicators": {
                "ml_prob_bullish": round(prob_up, 4),
                "decision_threshold": decision_threshold,
            },
        }
    except Exception as e:
        logger.error(f"Error predicting signal for {symbol}: {e}")
        return {"signal": "NO_TRADE", "confidence": 0,
                "reason": f"Prediction error: {e}", "bias": "NEUTRAL"}
