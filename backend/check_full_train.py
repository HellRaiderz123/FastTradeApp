"""
Full train test with new config: horizon=20, threshold=3%, BUY vs NO-BUY, regime features.
Uses 30 symbols for speed.
"""
import sys, os
sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", "postgresql://fasttrade:your_new_password@db:5432/fasttrade")

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score

from app.core.ml.config import StockMLConfig
from app.core.ml.dataset import build_stock_ml_dataset
from app.core.ml.stock_model import _per_symbol_split, _find_best_threshold
from app.core.ml.feature_builder import FEATURE_COLUMNS
from app.db.models_candles import CandleDaily
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

engine = create_engine(os.environ["DATABASE_URL"])
db = sessionmaker(bind=engine)()
config = StockMLConfig()
print(f"Config: horizon={config.horizon}, threshold={config.return_threshold}")
print(f"Features: {len(FEATURE_COLUMNS)} — {FEATURE_COLUMNS[-4:]}")

rows = db.query(CandleDaily.symbol, func.count().label("n"))\
         .group_by(CandleDaily.symbol).having(func.count() >= 500)\
         .order_by(func.count().desc()).limit(30).all()
symbols = [r.symbol for r in rows]

x, y = build_stock_ml_dataset(db, symbols, config)
print(f"\nDataset: {len(x)} rows, {y.mean():.1%} BUY, {(1-y.mean()):.1%} NO-BUY")

x_train, x_val, x_test, y_train, y_val, y_test = _per_symbol_split(x, y)
print(f"Split: train={len(x_train)} val={len(x_val)} test={len(x_test)}")
print(f"Train BUY%={y_train.mean():.1%}  Val BUY%={y_val.mean():.1%}  Test BUY%={y_test.mean():.1%}")

# Balance
df_b = x_train.drop(columns=["symbol"], errors="ignore").copy()
df_b["__l__"] = y_train.values
mn = df_b["__l__"].value_counts().min()
bal = pd.concat([df_b[df_b["__l__"]==c].sample(mn, random_state=42).sort_index() for c in [0,1]]).sort_index()
xb = bal.drop(columns=["__l__"]); yb = bal["__l__"]

x_val_f = x_val.drop(columns=["symbol"], errors="ignore")
x_test_f = x_test.drop(columns=["symbol"], errors="ignore")

pipe = Pipeline([("sc", StandardScaler()), ("clf", GradientBoostingClassifier(
    n_estimators=200, max_depth=4, learning_rate=0.05, subsample=0.8,
    min_samples_split=30, min_samples_leaf=15, max_features="sqrt", random_state=42))])
print("\nTraining (200 estimators)...")
pipe.fit(xb, yb)

y_val_proba = pipe.predict_proba(x_val_f)[:, 1]
best_t = _find_best_threshold(y_val.values, y_val_proba)
print(f"Calibrated threshold: {best_t}")

y_test_proba = pipe.predict_proba(x_test_f)[:, 1]
y_pred = (y_test_proba >= best_t).astype(int)

acc = (y_pred == y_test.values).mean()
p = precision_score(y_test, y_pred, zero_division=0)
r = recall_score(y_test, y_pred, zero_division=0)
f = f1_score(y_test, y_pred, zero_division=0)
auc = roc_auc_score(y_test, y_test_proba)

print(f"\n{'='*50}")
print(f"Accuracy : {acc:.2%}  (was 48.77%)")
print(f"Precision: {p:.2%}  (was 48.61%)")
print(f"Recall   : {r:.2%}  (was 57.74%)")
print(f"F1       : {f:.2%}  (was 52.78%)")
print(f"ROC-AUC  : {auc:.4f}  (was 0.4824)")
print(f"Pred rate: {y_pred.mean():.1%}")
print(f"{'='*50}")

# Feature importance
imp = dict(zip(FEATURE_COLUMNS, pipe.named_steps["clf"].feature_importances_))
print("\nTop 8 features:")
for feat, score in sorted(imp.items(), key=lambda kv: kv[1], reverse=True)[:8]:
    print(f"  {feat:25s}: {score:.4f}")
