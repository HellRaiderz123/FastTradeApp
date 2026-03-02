"""
Feature #16 — SHAP Feature-Importance Dashboard backend
Computes SHAP values for the trained ML model (single or ensemble) and
returns per-feature importance + waterfall data for the frontend.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.core.ml.config import StockMLConfig
from app.core.ml.dataset import _load_candles_df
from app.core.ml.feature_builder import FEATURE_COLUMNS, build_features_from_df
from app.core.ml.model_registry import load_model

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global SHAP values (average importance across dataset)
# ---------------------------------------------------------------------------


def compute_global_shap(
    db,
    config: StockMLConfig,
    *,
    max_samples: int = 300,
    model_type: str = "single",
) -> Dict[str, Any]:
    """
    Compute mean(|SHAP values|) across a sample of the training dataset.
    Returns a sorted list of {feature, importance, rank}.
    """
    import shap

    # Load model
    if model_type == "ensemble":
        from app.core.ml.ensemble import load_ensemble
        pipeline = load_ensemble(config)
    else:
        pipeline = load_model(config)

    if pipeline is None:
        return {"error": "Model not trained", "features": []}

    # Build a representative dataset
    from app.db.models_candles import CandleDaily
    from app.db.session import SessionLocal
    from sqlalchemy import func

    symbols_q = (
        db.query(CandleDaily.symbol)
        .group_by(CandleDaily.symbol)
        .having(func.count(CandleDaily.id) >= 500)
        .limit(20)
        .all()
    )
    symbols = [s[0] for s in symbols_q] if symbols_q else []

    frames: List[pd.DataFrame] = []
    for sym in symbols[:10]:
        raw = _load_candles_df(db, sym, config.timeframe, config.max_candles)
        if raw.empty:
            continue
        feats = build_features_from_df(raw, config)
        if not feats.empty:
            frames.append(feats[FEATURE_COLUMNS])

    if not frames:
        return {"error": "No feature data available", "features": []}

    X = pd.concat(frames, ignore_index=True)
    if len(X) > max_samples:
        X = X.sample(max_samples, random_state=42)

    # Use TreeExplainer if possible, otherwise KernelExplainer
    try:
        # For pipeline, extract the classifier step
        if hasattr(pipeline, "named_steps"):
            scaler = pipeline.named_steps.get("scaler")
            clf = pipeline.named_steps.get("clf")
            if scaler:
                X_scaled = pd.DataFrame(scaler.transform(X), columns=FEATURE_COLUMNS)
            else:
                X_scaled = X
        elif hasattr(pipeline, "gbm"):
            # Ensemble: use GBM's sub-model (has native tree SHAP)
            scaler = pipeline.gbm.named_steps.get("scaler")
            clf = pipeline.gbm.named_steps.get("clf")
            X_scaled = pd.DataFrame(scaler.transform(X), columns=FEATURE_COLUMNS) if scaler else X
        else:
            clf = pipeline
            X_scaled = X

        explainer = shap.TreeExplainer(clf)
        shap_values = explainer.shap_values(X_scaled)

        # shap_values shape: (n_samples, n_features) or list of 2
        if isinstance(shap_values, list):
            sv = np.array(shap_values[1])  # class-1 (bullish)
        elif shap_values.ndim == 3:
            sv = shap_values[:, :, 1]
        else:
            sv = shap_values

    except Exception as exc:
        logger.warning(f"TreeExplainer failed ({exc}), falling back to KernelExplainer")
        # Fallback: use model's predict_proba
        predict_fn = pipeline.predict_proba if hasattr(pipeline, "predict_proba") else pipeline.predict
        background = shap.kmeans(X, 50)
        explainer = shap.KernelExplainer(predict_fn, background)
        shap_values = explainer.shap_values(X.iloc[:100], nsamples=100)
        if isinstance(shap_values, list):
            sv = np.array(shap_values[1])
        else:
            sv = shap_values

    # Mean absolute SHAP value per feature
    mean_abs = np.abs(sv).mean(axis=0)
    order = np.argsort(mean_abs)[::-1]

    features = []
    for rank, idx in enumerate(order, start=1):
        features.append({
            "feature": FEATURE_COLUMNS[idx],
            "importance": round(float(mean_abs[idx]), 6),
            "rank": rank,
        })

    # Also return raw SHAP matrix summary (min/max/mean per feature) for bee-swarm
    shap_summary: List[Dict] = []
    for i, col in enumerate(FEATURE_COLUMNS):
        col_shap = sv[:, i]
        shap_summary.append({
            "feature": col,
            "mean": round(float(np.mean(col_shap)), 6),
            "std": round(float(np.std(col_shap)), 6),
            "min": round(float(np.min(col_shap)), 6),
            "max": round(float(np.max(col_shap)), 6),
            "abs_mean": round(float(np.abs(col_shap).mean()), 6),
        })

    return {
        "features": features,
        "shap_summary": sorted(shap_summary, key=lambda d: d["abs_mean"], reverse=True),
        "sample_count": len(X),
        "model_type": model_type,
    }


# ---------------------------------------------------------------------------
# Per-symbol SHAP waterfall (explain single prediction)
# ---------------------------------------------------------------------------


def compute_symbol_shap(
    db,
    symbol: str,
    config: StockMLConfig,
    *,
    model_type: str = "single",
) -> Dict[str, Any]:
    """
    Compute SHAP waterfall for the latest row of a given symbol.
    Returns base_value + per-feature contribution.
    """
    import shap

    if model_type == "ensemble":
        from app.core.ml.ensemble import load_ensemble
        pipeline = load_ensemble(config)
    else:
        pipeline = load_model(config)

    if pipeline is None:
        return {"error": "Model not trained"}

    raw = _load_candles_df(db, symbol, config.timeframe, config.max_candles)
    if raw.empty:
        return {"error": f"No candle data for {symbol}"}

    features = build_features_from_df(raw, config)
    if features.empty:
        return {"error": f"Not enough data to build features for {symbol}"}

    latest = features.iloc[-1:]
    x = latest[FEATURE_COLUMNS]

    # Resolve model
    if hasattr(pipeline, "named_steps"):
        scaler = pipeline.named_steps.get("scaler")
        clf = pipeline.named_steps.get("clf")
        x_scaled = pd.DataFrame(scaler.transform(x), columns=FEATURE_COLUMNS) if scaler else x
    elif hasattr(pipeline, "gbm"):
        scaler = pipeline.gbm.named_steps.get("scaler")
        clf = pipeline.gbm.named_steps.get("clf")
        x_scaled = pd.DataFrame(scaler.transform(x), columns=FEATURE_COLUMNS) if scaler else x
    else:
        clf = pipeline
        x_scaled = x

    try:
        explainer = shap.TreeExplainer(clf)
        sv = explainer.shap_values(x_scaled)
    except Exception:
        return {"error": "SHAP computation failed for this model type"}

    if isinstance(sv, list):
        vals = sv[1][0]
        base_value = float(explainer.expected_value[1]) if isinstance(explainer.expected_value, (list, np.ndarray)) else float(explainer.expected_value)
    elif sv.ndim == 3:
        vals = sv[0, :, 1]
        base_value = float(explainer.expected_value[1]) if isinstance(explainer.expected_value, (list, np.ndarray)) else float(explainer.expected_value)
    else:
        vals = sv[0]
        base_value = float(explainer.expected_value) if isinstance(explainer.expected_value, (float, np.floating)) else float(explainer.expected_value[0])

    waterfall: List[Dict] = []
    for i, col in enumerate(FEATURE_COLUMNS):
        waterfall.append({
            "feature": col,
            "value": round(float(x.iloc[0][col]), 6),
            "shap_value": round(float(vals[i]), 6),
        })

    # Sort by absolute contribution
    waterfall.sort(key=lambda d: abs(d["shap_value"]), reverse=True)

    # Prediction
    prob_up = float(pipeline.predict_proba(x)[0][1])

    return {
        "symbol": symbol,
        "base_value": round(base_value, 6),
        "prediction_prob_up": round(prob_up, 4),
        "waterfall": waterfall,
        "feature_values": {col: round(float(x.iloc[0][col]), 6) for col in FEATURE_COLUMNS},
    }
