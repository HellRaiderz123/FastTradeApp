"""
Verify _find_best_threshold picks a balanced threshold (not recall-biased).
Simulates a val set with 50/50 class balance and checks pred_rate guard.
"""
import numpy as np
import sys

sys.path.insert(0, "/app")
from app.core.ml.stock_model import _find_best_threshold

rng = np.random.default_rng(42)
n = 2000
y_true = rng.integers(0, 2, n)

# Simulate a model that outputs low probabilities (recall-biased scenario)
# UP class gets proba 0.40-0.65, DOWN gets 0.30-0.55 — overlapping
proba = np.where(y_true == 1,
                 rng.uniform(0.38, 0.65, n),
                 rng.uniform(0.28, 0.55, n))

t = _find_best_threshold(y_true, proba)
preds = (proba >= t).astype(int)
pred_rate = preds.mean()
from sklearn.metrics import precision_score, recall_score
p = precision_score(y_true, preds, zero_division=0)
r = recall_score(y_true, preds, zero_division=0)

print(f"Threshold selected : {t}")
print(f"Pred rate (UP%)    : {pred_rate:.2%}  (must be 20-70%)")
print(f"Precision          : {p:.2%}")
print(f"Recall             : {r:.2%}")
print(f"Geo-mean score     : {(p*r)**0.5:.4f}")
print()
ok = 0.20 <= pred_rate <= 0.70
print(f"Pred-rate guard OK : {ok}")
print(f"Precision >= 40%   : {p >= 0.40}")
print(f"Recall <= 80%      : {r <= 0.80}")
print(f"\nAll OK: {ok and p >= 0.40 and r <= 0.80}")
