"""
Feature #20 — Walk-Forward Optimization
Anchored walk-forward validation:
  Train on [0..t], test on [t..t+step], slide t forward.
Optionally tunes hyper-parameters per fold with Optuna.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.core.ml.config import StockMLConfig
from app.core.ml.dataset import build_stock_ml_dataset
from app.core.ml.feature_builder import FEATURE_COLUMNS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Walk-Forward Splitter
# ---------------------------------------------------------------------------


def _walk_forward_splits(
    n: int,
    *,
    min_train: int = 500,
    test_size: int = 100,
    step: int = 100,
) -> List[Tuple[range, range]]:
    """
    Generate (train_indices, test_indices) for anchored walk-forward.
    Training always starts from index 0 (expanding window).
    """
    splits = []
    train_end = min_train
    while train_end + test_size <= n:
        train_idx = range(0, train_end)
        test_idx = range(train_end, min(train_end + test_size, n))
        splits.append((train_idx, test_idx))
        train_end += step
    return splits


# ---------------------------------------------------------------------------
# Optuna hyper-parameter tuning (optional)
# ---------------------------------------------------------------------------


def _tune_hyperparams(
    x_train: pd.DataFrame,
    y_train: pd.Series,
    *,
    n_trials: int = 20,
    model_name: str = "gbm",
) -> Dict[str, Any]:
    """Run Optuna study to find best hyper-parameters for a fold."""
    try:
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)
    except ImportError:
        logger.warning("Optuna not installed, using defaults")
        return {}

    def objective(trial):
        if model_name == "xgb":
            try:
                from xgboost import XGBClassifier
                clf = XGBClassifier(
                    n_estimators=trial.suggest_int("n_estimators", 100, 400),
                    max_depth=trial.suggest_int("max_depth", 3, 8),
                    learning_rate=trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
                    subsample=trial.suggest_float("subsample", 0.6, 1.0),
                    colsample_bytree=trial.suggest_float("colsample_bytree", 0.5, 1.0),
                    min_child_weight=trial.suggest_int("min_child_weight", 5, 30),
                    reg_alpha=trial.suggest_float("reg_alpha", 0.01, 1.0, log=True),
                    use_label_encoder=False, eval_metric="logloss", verbosity=0, random_state=42,
                )
            except ImportError:
                return 0.0
        else:
            clf = GradientBoostingClassifier(
                n_estimators=trial.suggest_int("n_estimators", 100, 400),
                max_depth=trial.suggest_int("max_depth", 3, 8),
                learning_rate=trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
                subsample=trial.suggest_float("subsample", 0.6, 1.0),
                min_samples_split=trial.suggest_int("min_samples_split", 10, 40),
                min_samples_leaf=trial.suggest_int("min_samples_leaf", 5, 20),
                max_features="sqrt",
                random_state=42,
            )

        pipe = Pipeline([("scaler", StandardScaler()), ("clf", clf)])

        # Use last 20% of training data as validation
        split = int(len(x_train) * 0.8)
        x_t, x_v = x_train.iloc[:split], x_train.iloc[split:]
        y_t, y_v = y_train.iloc[:split], y_train.iloc[split:]

        pipe.fit(x_t, y_t)
        y_pred = pipe.predict(x_v)
        return float(f1_score(y_v, y_pred, zero_division=0))

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    return study.best_params


# ---------------------------------------------------------------------------
# Main walk-forward runner
# ---------------------------------------------------------------------------


def run_walk_forward(
    db,
    symbols: List[str],
    config: StockMLConfig,
    *,
    min_train: int = 500,
    test_size: int = 100,
    step: int = 100,
    model_name: str = "gbm",
    optimize: bool = False,
    optuna_trials: int = 15,
) -> Dict[str, Any]:
    """
    Walk-forward cross-validation pipeline.
    Returns per-fold metrics + aggregated OOS performance.
    """
    x, y = build_stock_ml_dataset(db, symbols, config)
    if x.empty or len(x) < min_train + test_size:
        return {
            "error": f"Not enough data ({len(x)} rows, need {min_train + test_size})",
            "folds": [],
        }

    splits = _walk_forward_splits(len(x), min_train=min_train, test_size=test_size, step=step)
    if not splits:
        return {"error": "Could not generate walk-forward splits", "folds": []}

    logger.info(f"📈 Walk-forward: {len(splits)} folds, model={model_name}, optimize={optimize}")

    fold_results: List[Dict[str, Any]] = []
    all_oos_preds: List[int] = []
    all_oos_true: List[int] = []
    all_oos_proba: List[float] = []

    for fold_idx, (train_idx, test_idx) in enumerate(splits):
        x_train = x.iloc[list(train_idx)]
        y_train = y.iloc[list(train_idx)]
        x_test = x.iloc[list(test_idx)]
        y_test = y.iloc[list(test_idx)]

        # Optional Optuna tuning
        best_params: Dict[str, Any] = {}
        if optimize:
            best_params = _tune_hyperparams(x_train, y_train, n_trials=optuna_trials, model_name=model_name)

        # Build classifier
        if model_name == "xgb":
            try:
                from xgboost import XGBClassifier
                clf = XGBClassifier(
                    use_label_encoder=False, eval_metric="logloss",
                    verbosity=0, random_state=42, **best_params,
                )
            except ImportError:
                clf = GradientBoostingClassifier(random_state=42, **best_params)
        elif model_name == "rf":
            from sklearn.ensemble import RandomForestClassifier
            clf = RandomForestClassifier(
                n_jobs=-1, random_state=42, class_weight="balanced", **best_params,
            )
        else:
            clf = GradientBoostingClassifier(random_state=42, **best_params)

        pipe = Pipeline([("scaler", StandardScaler()), ("clf", clf)])
        pipe.fit(x_train, y_train)

        y_pred = pipe.predict(x_test)
        try:
            y_proba = pipe.predict_proba(x_test)[:, 1]
        except Exception:
            y_proba = np.zeros(len(y_test))

        acc = float(accuracy_score(y_test, y_pred))
        prec = float(precision_score(y_test, y_pred, zero_division=0))
        rec = float(recall_score(y_test, y_pred, zero_division=0))
        f1 = float(f1_score(y_test, y_pred, zero_division=0))
        try:
            roc = float(roc_auc_score(y_test, y_proba))
        except Exception:
            roc = 0.0

        fold_results.append({
            "fold": fold_idx + 1,
            "train_rows": len(train_idx),
            "test_rows": len(test_idx),
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
            "roc_auc": round(roc, 4),
            "best_params": best_params if optimize else None,
        })

        all_oos_preds.extend(y_pred.tolist())
        all_oos_true.extend(y_test.tolist())
        all_oos_proba.extend(y_proba.tolist())

        logger.info(
            f"  Fold {fold_idx + 1}/{len(splits)}: acc={acc:.4f}, f1={f1:.4f}, "
            f"train={len(train_idx)}, test={len(test_idx)}"
        )

    # Aggregate OOS metrics
    oos_acc = float(accuracy_score(all_oos_true, all_oos_preds))
    oos_prec = float(precision_score(all_oos_true, all_oos_preds, zero_division=0))
    oos_rec = float(recall_score(all_oos_true, all_oos_preds, zero_division=0))
    oos_f1 = float(f1_score(all_oos_true, all_oos_preds, zero_division=0))
    try:
        oos_roc = float(roc_auc_score(all_oos_true, all_oos_proba))
    except Exception:
        oos_roc = 0.0

    # Stability metrics
    accs = [f["accuracy"] for f in fold_results]
    f1s = [f["f1_score"] for f in fold_results]

    return {
        "model_name": model_name,
        "optimize": optimize,
        "total_folds": len(fold_results),
        "total_oos_samples": len(all_oos_true),
        "symbols_count": len(symbols),
        "aggregate_oos": {
            "accuracy": round(oos_acc, 4),
            "precision": round(oos_prec, 4),
            "recall": round(oos_rec, 4),
            "f1_score": round(oos_f1, 4),
            "roc_auc": round(oos_roc, 4),
        },
        "stability": {
            "accuracy_mean": round(float(np.mean(accs)), 4),
            "accuracy_std": round(float(np.std(accs)), 4),
            "f1_mean": round(float(np.mean(f1s)), 4),
            "f1_std": round(float(np.std(f1s)), 4),
            "worst_fold_accuracy": round(float(np.min(accs)), 4),
            "best_fold_accuracy": round(float(np.max(accs)), 4),
        },
        "folds": fold_results,
        "fold_accuracy_series": [{"fold": f["fold"], "accuracy": f["accuracy"], "f1": f["f1_score"]} for f in fold_results],
    }
