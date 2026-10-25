"""
Feature #15 — Model Ensemble (GBM + RandomForest + XGBoost voting)
Soft-voting ensemble: averages predicted probabilities from three models.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.core.ml.config import StockMLConfig
from app.core.ml.dataset import build_stock_ml_dataset
from app.core.ml.feature_builder import FEATURE_COLUMNS
from app.core.ml.model_registry import ensure_model_dir
from app.core.ml.overfitting import check_overfitting

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports – packages may not be installed on every host
# ---------------------------------------------------------------------------

def _get_xgb():
    from xgboost import XGBClassifier
    return XGBClassifier

def _get_lgb():
    from lightgbm import LGBMClassifier
    return LGBMClassifier




class EnsembleModel:
    """Soft-voting ensemble wrapping three heterogeneous classifiers."""

    def __init__(
        self,
        gbm: Pipeline,
        rf: Pipeline,
        xgb: Pipeline,
        weights: Tuple[float, float, float] = (0.35, 0.30, 0.35),
    ):
        self.gbm = gbm
        self.rf = rf
        self.xgb = xgb
        # Normalize weights so they always sum to 1.0
        w = np.array(weights, dtype=float)
        self.weights = tuple(w / w.sum())
        self.classes_ = np.array([0, 1])

    # -- Scikit-learn–compatible interface -----------------------------------
    def predict_proba(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        p_gbm = self.gbm.predict_proba(X)
        p_rf = self.rf.predict_proba(X)
        p_xgb = self.xgb.predict_proba(X)
        avg = (
            self.weights[0] * p_gbm
            + self.weights[1] * p_rf
            + self.weights[2] * p_xgb
        )
        return avg

    def predict(self, X) -> np.ndarray:
        proba = self.predict_proba(X)
        return np.argmax(proba, axis=1)

    def score(self, X, y) -> float:
        return float(accuracy_score(y, self.predict(X)))

    # -- per-model probabilities (for diagnostics) --------------------------
    def per_model_proba(self, X) -> Dict[str, np.ndarray]:
        return {
            "gbm": self.gbm.predict_proba(X),
            "rf": self.rf.predict_proba(X),
            "xgb": self.xgb.predict_proba(X),
        }

    # -- per-model feature importances --------------------------------------
    def feature_importances(self) -> Dict[str, Dict[str, float]]:
        result: Dict[str, Dict[str, float]] = {}
        for name, pipe in [("gbm", self.gbm), ("rf", self.rf), ("xgb", self.xgb)]:
            try:
                clf = pipe.named_steps.get("clf") or pipe[-1]
                imp = clf.feature_importances_
                result[name] = dict(zip(FEATURE_COLUMNS, imp.tolist()))
            except Exception:
                result[name] = {}
        return result


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def _per_symbol_split(
    x: pd.DataFrame, y: pd.Series, test_ratio: float = 0.2, val_ratio: float = 0.1
) -> Tuple:
    """Per-symbol chronological split: train=70% / val=10% / test=20%."""
    train_idx, val_idx, test_idx = [], [], []
    sym_col = "symbol" if "symbol" in x.columns else None
    if sym_col is None:
        n = len(x)
        t_cut = int(n * (1 - test_ratio - val_ratio))
        v_cut = int(n * (1 - test_ratio))
        return x.iloc[:t_cut], x.iloc[t_cut:v_cut], x.iloc[v_cut:], y.iloc[:t_cut], y.iloc[t_cut:v_cut], y.iloc[v_cut:]
    for _, grp in x.groupby(sym_col, sort=False):
        idx = grp.index.tolist()
        n = len(idx)
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
        y.loc[train_idx], y.loc[val_idx], y.loc[test_idx],
    )


def _find_best_threshold(y_true: np.ndarray, y_proba: np.ndarray) -> float:
    """
    Find the best operating threshold on the val set.
    Requires minimum 40% precision (to pass diagnostics) while maximizing F1.
    """
    from sklearn.metrics import precision_score as _p, recall_score as _r, f1_score as _f1
    n = len(y_true)
    if n < 50:
        return 0.50

    candidates = []
    
    for t in np.arange(0.30, 0.75, 0.01):
        preds = (y_proba >= t).astype(int)
        pred_rate = preds.sum() / n
        if pred_rate < 0.10 or pred_rate > 0.60:
            continue
        p = _p(y_true, preds, zero_division=0)
        r = _r(y_true, preds, zero_division=0)
        f = _f1(y_true, preds, zero_division=0)
        candidates.append((round(t, 2), p, r, f, pred_rate))

    if not candidates:
        logger.warning(f"Threshold search: no valid threshold. Using 0.50")
        return 0.50

    # Priority 1: precision >= 40% AND recall >= 15%, maximize F1
    valid = [(t, p, r, f, pr) for t, p, r, f, pr in candidates if p >= 0.40 and r >= 0.15]
    if valid:
        best = max(valid, key=lambda x: x[3])  # Best F1
        logger.info(f"Threshold: t={best[0]}, prec={best[1]:.3f}, rec={best[2]:.3f}, f1={best[3]:.3f}, pred_rate={best[4]:.3f}")
        return best[0]

    # Priority 2: precision >= 40%, any recall - maximize recall
    valid_prec = [(t, p, r, f, pr) for t, p, r, f, pr in candidates if p >= 0.40]
    if valid_prec:
        best = max(valid_prec, key=lambda x: x[2])  # Best recall
        logger.info(f"Threshold (prec-only): t={best[0]}, prec={best[1]:.3f}, rec={best[2]:.3f}, f1={best[3]:.3f}")
        return best[0]

    # Priority 3: best precision available (model may be weak)
    best = max(candidates, key=lambda x: x[1])
    logger.warning(f"Threshold (best-prec): t={best[0]}, prec={best[1]:.3f}, rec={best[2]:.3f}, f1={best[3]:.3f}")
    return best[0]


def _build_gbm_pipeline(y_train: pd.Series) -> Pipeline:
    n_pos = int(y_train.sum())
    n_neg = len(y_train) - n_pos
    # Balanced class weight with cap
    pos_weight = min(n_neg / max(n_pos, 1), 2.5) if n_neg > n_pos else 1.0
    
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf", GradientBoostingClassifier(
            n_estimators=150, max_depth=3, learning_rate=0.08,
            subsample=0.8, min_samples_split=30, min_samples_leaf=15,
            max_features="sqrt", random_state=42,
        )),
    ]), pos_weight


def _build_rf_pipeline(y_train: pd.Series) -> Pipeline:
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf", RandomForestClassifier(
            n_estimators=200, max_depth=6, min_samples_split=30,
            min_samples_leaf=15, max_features="sqrt",
            class_weight="balanced_subsample",  # Handle imbalance
            random_state=42, n_jobs=-1,
        )),
    ])


def _build_xgb_pipeline(y_train: pd.Series) -> Pipeline:
    XGBClassifier = _get_xgb()
    n_pos = int(y_train.sum())
    n_neg = len(y_train) - n_pos
    # Cap scale_pos_weight to prevent over-correction
    scale_pos_weight = min(n_neg / max(n_pos, 1), 2.5)
    
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf", XGBClassifier(
            n_estimators=150, max_depth=3, learning_rate=0.08,
            subsample=0.8, colsample_bytree=0.8,
            min_child_weight=15, reg_alpha=0.3, reg_lambda=1.5,
            scale_pos_weight=scale_pos_weight,
            eval_metric="logloss", random_state=42, n_jobs=-1, verbosity=0,
        )),
    ])



def train_ensemble(
    db,
    symbols: List[str],
    config: StockMLConfig,
) -> Dict[str, Any]:
    """Train the 3-model ensemble and persist artefacts."""
    import joblib

    x, y = build_stock_ml_dataset(db, symbols, config)
    if x.empty or len(x) < config.min_rows:
        raise ValueError(f"Not enough data ({len(x)} rows, need {config.min_rows})")

    class_counts = y.value_counts()
    logger.info(f"📊 Ensemble dataset: {len(x)} samples, Classes: {dict(class_counts)}")

    x_train, x_val, x_test, y_train, y_val, y_test = _per_symbol_split(x, y)

    # Balance training set — undersample majority class
    # x_train, y_train = _balance_train(x_train, y_train) //as per google
    logger.info(f"📊 Full chronological train: {len(x_train)} rows")

    # Build & fit each pipeline with class balancing
    gbm, gbm_pos_weight = _build_gbm_pipeline(y_train)
    rf  = _build_rf_pipeline(y_train)
    xgb = _build_xgb_pipeline(y_train)

    # Sample weights for GBM
    sample_weight = np.where(y_train.values == 1, gbm_pos_weight, 1.0).astype(float)

    logger.info("🔧 Training GBM …")
    gbm.fit(x_train, y_train, clf__sample_weight=sample_weight)
    logger.info("🔧 Training RandomForest …")
    rf.fit(x_train, y_train)
    logger.info("🔧 Training XGBoost …")
    xgb.fit(x_train, y_train)

    ensemble = EnsembleModel(gbm, rf, xgb)

    # --- Calibrate threshold on val set ------------------------------------
    y_val_proba = ensemble.predict_proba(x_val)[:, 1]
    best_threshold = _find_best_threshold(y_val.values, y_val_proba)
    logger.info(f"📊 Ensemble calibrated threshold: {best_threshold}")

    # --- Evaluate on held-out test set -------------------------------------
    y_proba = ensemble.predict_proba(x_test)[:, 1]
    y_pred  = (y_proba >= best_threshold).astype(int)

    accuracy  = float((y_pred == y_test.values).mean())
    precision = float(precision_score(y_test, y_pred, zero_division=0))
    recall_val = float(recall_score(y_test, y_pred, zero_division=0))
    f1        = float(f1_score(y_test, y_pred, zero_division=0))
    try:
        roc_auc = float(roc_auc_score(y_test, y_proba))
    except Exception:
        roc_auc = 0.0
    cm = confusion_matrix(y_test, y_pred).tolist()
    class_report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)

    # Per-model accuracy (using calibrated threshold)
    per_model = {}
    for name, pipe in [("gbm", gbm), ("rf", rf), ("xgb", xgb)]:
        p = pipe.predict_proba(x_test)[:, 1]
        pred = (p >= best_threshold).astype(int)
        per_model[name] = round(float((pred == y_test.values).mean()), 4)

    feat_imp = ensemble.feature_importances()

    # Train accuracy for overfitting check
    y_train_proba = ensemble.predict_proba(x_train)[:, 1]
    y_train_pred = (y_train_proba >= best_threshold).astype(int)
    train_accuracy = float((y_train_pred == y_train.values).mean())

    # Overfitting diagnostics
    overfit_report = check_overfitting(
        train_accuracy=train_accuracy,
        test_accuracy=accuracy,
        test_precision=precision,
        test_recall=recall_val,
        test_f1=f1,
        test_roc_auc=roc_auc,
        y_test=y_test.values,
        y_pred=y_pred,
    )
    logger.info(f"🔍 Ensemble verdict: {overfit_report['verdict']} (score={overfit_report['usability_score']})")

    logger.info(
        f"✅ Ensemble trained: acc={accuracy:.4f}, prec={precision:.4f}, "
        f"recall={recall_val:.4f}, f1={f1:.4f}, roc_auc={roc_auc:.4f}"
    )
    logger.info(f"   Per-model accuracy: {per_model}")

    metadata: Dict[str, Any] = {
        "model_type": "Ensemble_GBM_RF_XGB",
        "weights": list(ensemble.weights),
        "decision_threshold": best_threshold,
        "timeframe": config.timeframe,
        "horizon": config.horizon,
        "return_threshold": config.return_threshold,
        "train_rows": int(len(x_train)),
        "val_rows": int(len(x_val)),
        "test_rows": int(len(x_test)),
        "total_samples": int(len(x)),
        "train_accuracy": round(train_accuracy, 4),
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall_val, 4),
        "f1_score": round(f1, 4),
        "roc_auc": round(roc_auc, 4),
        "confusion_matrix": cm,
        "classification_report": class_report,
        "per_model_accuracy": per_model,
        "feature_importance": feat_imp,
        "feature_columns": FEATURE_COLUMNS,
        "symbols_count": len(symbols),
        "class_distribution": {str(k): int(v) for k, v in class_counts.items()},
        "training_date": datetime.now().isoformat(),
        "overfitting": overfit_report,
    }

    # Persist
    ensure_model_dir(config)
    ensemble_path = config.model_dir / "ensemble_model.joblib"
    meta_path = config.model_dir / "ensemble_model.json"
    joblib.dump(ensemble, ensemble_path)
    import json
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    return metadata


def load_ensemble(config: StockMLConfig) -> Optional[EnsembleModel]:
    """Load persisted ensemble model."""
    import joblib
    path = config.model_dir / "ensemble_model.joblib"
    if not path.exists():
        return None
    return joblib.load(path)


def load_ensemble_metadata(config: StockMLConfig) -> Dict[str, Any]:
    import json
    path = config.model_dir / "ensemble_model.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def predict_ensemble(db, symbol: str, config: StockMLConfig) -> Dict[str, Any]:
    """Predict using ensemble; fall back to single GBM if ensemble not available."""
    ensemble = load_ensemble(config)
    if ensemble is None:
        return {"signal": "NO_TRADE", "confidence": 0, "reason": "Ensemble not trained", "bias": "NEUTRAL"}

    # Load calibrated threshold from saved metadata
    meta = load_ensemble_metadata(config)
    decision_threshold = meta.get("decision_threshold", 0.5)

    from app.core.ml.dataset import _load_candles_df
    from app.core.ml.feature_builder import build_features_from_df

    raw = _load_candles_df(db, symbol, config.timeframe, config.max_candles)
    if raw.empty:
        return {"signal": "NO_TRADE", "confidence": 0, "reason": "No candle data", "bias": "NEUTRAL"}

    features = build_features_from_df(raw, config)
    if features.empty:
        return {"signal": "NO_TRADE", "confidence": 0, "reason": "Not enough feature rows", "bias": "NEUTRAL"}

    x = features.iloc[-1:][FEATURE_COLUMNS]
    prob_up = float(ensemble.predict_proba(x)[0][1])

    per = ensemble.per_model_proba(x)
    per_model = {name: round(float(p[0][1]), 4) for name, p in per.items()}

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
        "reason": f"Ensemble prob_up={prob_up:.3f} threshold={decision_threshold} (gbm={per_model.get('gbm',0)}, rf={per_model.get('rf',0)}, xgb={per_model.get('xgb',0)})",
        "bias": bias,
        "indicators": {
            "ensemble_prob_up": round(prob_up, 4),
            "decision_threshold": decision_threshold,
            "per_model": per_model,
        },
    }
