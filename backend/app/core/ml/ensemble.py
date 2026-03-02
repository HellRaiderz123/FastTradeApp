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

# ---------------------------------------------------------------------------
# Ensemble wrapper
# ---------------------------------------------------------------------------


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
        self.weights = weights
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

def _temporal_split(x: pd.DataFrame, y: pd.Series, test_ratio: float = 0.2):
    split_idx = int(len(x) * (1 - test_ratio))
    return x.iloc[:split_idx], x.iloc[split_idx:], y.iloc[:split_idx], y.iloc[split_idx:]


def _build_gbm_pipeline() -> Pipeline:
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf", GradientBoostingClassifier(
            n_estimators=200, max_depth=5, learning_rate=0.1,
            subsample=0.8, min_samples_split=20, min_samples_leaf=10,
            max_features="sqrt", random_state=42,
        )),
    ])


def _build_rf_pipeline() -> Pipeline:
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf", RandomForestClassifier(
            n_estimators=300, max_depth=8, min_samples_split=20,
            min_samples_leaf=10, max_features="sqrt",
            class_weight="balanced", random_state=42, n_jobs=-1,
        )),
    ])


def _build_xgb_pipeline() -> Pipeline:
    XGBClassifier = _get_xgb()
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf", XGBClassifier(
            n_estimators=250, max_depth=5, learning_rate=0.08,
            subsample=0.8, colsample_bytree=0.8,
            min_child_weight=10, reg_alpha=0.1, reg_lambda=1.0,
            use_label_encoder=False, eval_metric="logloss",
            random_state=42, n_jobs=-1, verbosity=0,
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

    x_train, x_test, y_train, y_test = _temporal_split(x, y)

    # Build & fit each pipeline
    gbm = _build_gbm_pipeline()
    rf = _build_rf_pipeline()
    xgb = _build_xgb_pipeline()

    logger.info("🔧 Training GBM …")
    gbm.fit(x_train, y_train)
    logger.info("🔧 Training RandomForest …")
    rf.fit(x_train, y_train)
    logger.info("🔧 Training XGBoost …")
    xgb.fit(x_train, y_train)

    ensemble = EnsembleModel(gbm, rf, xgb)

    # --- Evaluate ----------------------------------------------------------
    y_pred = ensemble.predict(x_test)
    y_proba = ensemble.predict_proba(x_test)[:, 1]

    accuracy = float(accuracy_score(y_test, y_pred))
    precision = float(precision_score(y_test, y_pred, zero_division=0))
    recall_val = float(recall_score(y_test, y_pred, zero_division=0))
    f1 = float(f1_score(y_test, y_pred, zero_division=0))
    try:
        roc_auc = float(roc_auc_score(y_test, y_proba))
    except Exception:
        roc_auc = 0.0
    cm = confusion_matrix(y_test, y_pred).tolist()
    class_report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)

    # Per-model accuracy
    per_model = {}
    for name, pipe in [("gbm", gbm), ("rf", rf), ("xgb", xgb)]:
        acc = float(pipe.score(x_test, y_test))
        per_model[name] = round(acc, 4)

    # Feature importances
    feat_imp = ensemble.feature_importances()

    logger.info(
        f"✅ Ensemble trained: acc={accuracy:.4f}, prec={precision:.4f}, "
        f"recall={recall_val:.4f}, f1={f1:.4f}, roc_auc={roc_auc:.4f}"
    )
    logger.info(f"   Per-model accuracy: {per_model}")

    metadata: Dict[str, Any] = {
        "model_type": "Ensemble_GBM_RF_XGB",
        "weights": list(ensemble.weights),
        "timeframe": config.timeframe,
        "horizon": config.horizon,
        "return_threshold": config.return_threshold,
        "train_rows": int(len(x_train)),
        "test_rows": int(len(x_test)),
        "total_samples": int(len(x)),
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

    from app.core.ml.dataset import _load_candles_df
    from app.core.ml.feature_builder import build_features_from_df

    raw = _load_candles_df(db, symbol, config.timeframe, config.max_candles)
    if raw.empty:
        return {"signal": "NO_TRADE", "confidence": 0, "reason": "No candle data", "bias": "NEUTRAL"}

    features = build_features_from_df(raw, config)
    if features.empty:
        return {"signal": "NO_TRADE", "confidence": 0, "reason": "Not enough feature rows", "bias": "NEUTRAL"}

    latest = features.iloc[-1:]
    x = latest[FEATURE_COLUMNS]

    # Ensemble probability
    prob_up = float(ensemble.predict_proba(x)[0][1])

    # Per-model breakdown
    per = ensemble.per_model_proba(x)
    per_model = {
        name: round(float(p[0][1]), 4) for name, p in per.items()
    }

    # Map to signal
    if prob_up >= config.bullish_prob_threshold:
        signal, bias = "BULLISH", "BULLISH"
    elif prob_up <= config.bearish_prob_threshold:
        signal, bias = "BEARISH", "BEARISH"
    else:
        signal, bias = "NO_TRADE", "NEUTRAL"

    confidence = int(max(prob_up, 1 - prob_up) * 100)

    return {
        "signal": signal,
        "confidence": confidence,
        "reason": f"Ensemble prob_up={prob_up:.3f} (gbm={per_model.get('gbm',0)}, rf={per_model.get('rf',0)}, xgb={per_model.get('xgb',0)})",
        "bias": bias,
        "indicators": {
            "ensemble_prob_up": round(prob_up, 4),
            "per_model": per_model,
        },
    }
