"""
Overfitting and model quality diagnostics.

Checks applied to every trained model:
  1. Train/test accuracy gap          — large gap = overfitting
  2. ROC-AUC floor                    — below 0.52 = no better than random
  3. Precision floor                  — below 0.50 = too many false signals
  4. Recall ceiling                   — above 0.90 = predicting everything as BUY
  5. F1 floor                         — below 0.45 = overall too weak
  6. Prediction rate guard            — outside 15-85% = degenerate classifier
  7. Class-conditional accuracy       — one class much worse than the other
  8. LSTM-specific: val loss divergence from train loss
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────
THRESHOLDS = {
    "max_train_test_acc_gap": 0.12,   # >12% gap = overfitting
    "min_roc_auc":            0.52,   # below = random
    "min_precision":          0.50,   # below = too many false signals
    "max_recall":             0.90,   # above = predicting everything as BUY
    "min_f1":                 0.45,   # below = overall too weak
    "min_pred_rate":          0.15,   # below = almost never fires
    "max_pred_rate":          0.85,   # above = fires on everything
    "max_class_acc_gap":      0.30,   # >30% gap between class-0 and class-1 accuracy
    "max_lstm_loss_gap":      0.15,   # val_loss - train_loss > 0.15 = LSTM overfitting
}


# ── Severity levels ───────────────────────────────────────────────────────────
CRITICAL = "critical"   # model should NOT be used
WARNING  = "warning"    # model is usable but degraded
INFO     = "info"       # informational note


def _flag(level: str, code: str, message: str, value: Any = None, threshold: Any = None) -> Dict:
    return {
        "level":     level,
        "code":      code,
        "message":   message,
        "value":     round(float(value), 4) if value is not None else None,
        "threshold": threshold,
    }


# ── Core diagnostic function ──────────────────────────────────────────────────

def check_overfitting(
    *,
    train_accuracy: float,
    test_accuracy:  float,
    test_precision: float,
    test_recall:    float,
    test_f1:        float,
    test_roc_auc:   float,
    y_test:         np.ndarray,
    y_pred:         np.ndarray,
    # LSTM-only (optional)
    train_loss_history: Optional[List[float]] = None,
    val_loss_history:   Optional[List[float]] = None,
) -> Dict[str, Any]:
    """
    Run all overfitting and quality checks.
    Returns a structured report with flags, an overall verdict, and a
    usability score (0-100).
    """
    flags: List[Dict] = []
    t = THRESHOLDS

    # 1. Train/test accuracy gap
    gap = train_accuracy - test_accuracy
    if gap > t["max_train_test_acc_gap"]:
        flags.append(_flag(
            CRITICAL, "OVERFIT_ACC_GAP",
            f"Train accuracy ({train_accuracy:.1%}) is {gap:.1%} higher than test ({test_accuracy:.1%}). "
            "Model memorised training data.",
            gap, t["max_train_test_acc_gap"]
        ))
    elif gap > t["max_train_test_acc_gap"] * 0.6:
        flags.append(_flag(
            WARNING, "OVERFIT_ACC_GAP_MILD",
            f"Mild train/test gap ({gap:.1%}). Monitor after retraining.",
            gap, t["max_train_test_acc_gap"]
        ))

    # 2. ROC-AUC floor
    if test_roc_auc < t["min_roc_auc"]:
        flags.append(_flag(
            CRITICAL, "LOW_ROC_AUC",
            f"ROC-AUC {test_roc_auc:.3f} is near random (0.50). Model has no discriminative power.",
            test_roc_auc, t["min_roc_auc"]
        ))
    elif test_roc_auc < 0.55:
        flags.append(_flag(
            WARNING, "WEAK_ROC_AUC",
            f"ROC-AUC {test_roc_auc:.3f} is weak. Predictions are only slightly better than random.",
            test_roc_auc, 0.55
        ))

    # 3. Precision floor
    if test_precision < t["min_precision"]:
        flags.append(_flag(
            CRITICAL, "LOW_PRECISION",
            f"Precision {test_precision:.1%} — more than half of BUY signals are wrong. "
            "This will generate losing trades.",
            test_precision, t["min_precision"]
        ))

    # 4. Recall ceiling (predicting everything as BUY)
    if test_recall > t["max_recall"]:
        flags.append(_flag(
            CRITICAL, "HIGH_RECALL_BIAS",
            f"Recall {test_recall:.1%} is too high — model is predicting BUY on almost everything. "
            "Likely a degenerate classifier.",
            test_recall, t["max_recall"]
        ))

    # 5. F1 floor
    if test_f1 < t["min_f1"]:
        flags.append(_flag(
            WARNING, "LOW_F1",
            f"F1 score {test_f1:.1%} is below minimum threshold. "
            "Model is not reliable enough for trading signals.",
            test_f1, t["min_f1"]
        ))

    # 6. Prediction rate guard
    if len(y_pred) > 0:
        pred_rate = float(y_pred.mean())
        if pred_rate < t["min_pred_rate"]:
            flags.append(_flag(
                CRITICAL, "LOW_PRED_RATE",
                f"Model predicts BUY only {pred_rate:.1%} of the time — almost never fires.",
                pred_rate, t["min_pred_rate"]
            ))
        elif pred_rate > t["max_pred_rate"]:
            flags.append(_flag(
                CRITICAL, "HIGH_PRED_RATE",
                f"Model predicts BUY {pred_rate:.1%} of the time — fires on almost everything.",
                pred_rate, t["max_pred_rate"]
            ))

    # 7. Class-conditional accuracy gap
    if len(y_test) > 0 and len(y_pred) > 0:
        mask_0 = y_test == 0
        mask_1 = y_test == 1
        acc_0 = float((y_pred[mask_0] == 0).mean()) if mask_0.sum() > 0 else 0.0
        acc_1 = float((y_pred[mask_1] == 1).mean()) if mask_1.sum() > 0 else 0.0
        class_gap = abs(acc_0 - acc_1)
        if class_gap > t["max_class_acc_gap"]:
            worse_class = "DOWN" if acc_0 < acc_1 else "UP"
            flags.append(_flag(
                WARNING, "CLASS_IMBALANCE_BIAS",
                f"Class accuracy gap {class_gap:.1%} — model is biased toward {worse_class} signals. "
                f"(UP acc={acc_1:.1%}, DOWN acc={acc_0:.1%})",
                class_gap, t["max_class_acc_gap"]
            ))

    # 8. LSTM loss divergence
    if train_loss_history and val_loss_history and len(train_loss_history) > 5:
        # Compare last 5 epochs
        final_train_loss = float(np.mean(train_loss_history[-5:]))
        final_val_loss   = float(np.mean(val_loss_history[-5:]))
        loss_gap = final_val_loss - final_train_loss
        if loss_gap > t["max_lstm_loss_gap"]:
            flags.append(_flag(
                CRITICAL, "LSTM_LOSS_DIVERGENCE",
                f"LSTM val_loss ({final_val_loss:.4f}) is {loss_gap:.4f} above train_loss ({final_train_loss:.4f}). "
                "Model is overfitting — increase dropout or reduce epochs.",
                loss_gap, t["max_lstm_loss_gap"]
            ))
        elif loss_gap > t["max_lstm_loss_gap"] * 0.5:
            flags.append(_flag(
                WARNING, "LSTM_LOSS_GAP_MILD",
                f"Mild LSTM loss gap ({loss_gap:.4f}). Watch for overfitting.",
                loss_gap, t["max_lstm_loss_gap"]
            ))

    # ── Verdict ───────────────────────────────────────────────────────────────
    critical_flags = [f for f in flags if f["level"] == CRITICAL]
    warning_flags  = [f for f in flags if f["level"] == WARNING]

    # Usability score: start at 100, deduct per flag
    score = 100
    score -= len(critical_flags) * 25
    score -= len(warning_flags)  * 8
    score = max(0, min(100, score))

    if critical_flags:
        verdict = "NOT_USABLE"
        verdict_message = (
            f"{len(critical_flags)} critical issue(s) found. "
            "Do NOT use this model for live or paper trading."
        )
    elif len(warning_flags) >= 3:
        verdict = "WEAK"
        verdict_message = (
            f"{len(warning_flags)} warnings. Model is marginal — retrain with more data or tune hyperparameters."
        )
    elif warning_flags:
        verdict = "ACCEPTABLE"
        verdict_message = (
            f"{len(warning_flags)} warning(s). Model is usable but not optimal."
        )
    else:
        verdict = "GOOD"
        verdict_message = "No issues detected. Model passed all quality checks."

    logger.info(
        f"🔍 Overfitting check: verdict={verdict}, score={score}, "
        f"critical={len(critical_flags)}, warnings={len(warning_flags)}"
    )
    for f in flags:
        log_fn = logger.warning if f["level"] != INFO else logger.info
        log_fn(f"  [{f['level'].upper()}] {f['code']}: {f['message']}")

    return {
        "verdict":         verdict,
        "verdict_message": verdict_message,
        "usability_score": score,
        "critical_count":  len(critical_flags),
        "warning_count":   len(warning_flags),
        "flags":           flags,
        "metrics_summary": {
            "train_accuracy": round(train_accuracy, 4),
            "test_accuracy":  round(test_accuracy, 4),
            "train_test_gap": round(train_accuracy - test_accuracy, 4),
            "roc_auc":        round(test_roc_auc, 4),
            "precision":      round(test_precision, 4),
            "recall":         round(test_recall, 4),
            "f1":             round(test_f1, 4),
        },
    }
