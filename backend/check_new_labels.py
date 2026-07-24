"""
Verify new label params (horizon=10, threshold=3%) improve feature signal.
"""
import sys, os
sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", "postgresql://fasttrade:your_new_password@db:5432/fasttrade")

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sklearn.metrics import roc_auc_score
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

from app.core.ml.config import StockMLConfig
from app.core.ml.dataset import build_stock_ml_dataset
from app.core.ml.stock_model import _per_symbol_split
from app.core.ml.feature_builder import FEATURE_COLUMNS
from app.db.models_candles import CandleDaily

engine = create_engine(os.environ["DATABASE_URL"])
db = sessionmaker(bind=engine)()
config = StockMLConfig()
print(f"Config: horizon={config.horizon}, return_threshold={config.return_threshold}")

rows = db.query(CandleDaily.symbol, func.count().label("n"))\
         .group_by(CandleDaily.symbol).having(func.count() >= 500)\
         .order_by(func.count().desc()).all()
symbols = [r.symbol for r in rows]

x, y = build_stock_ml_dataset(db, symbols, config)
print(f"Dataset: {len(x)} rows, {y.mean():.1%} UP")

x_feat = x.drop(columns=["symbol"], errors="ignore")

print("\n--- Per-feature ROC-AUC (top 10) ---")
aucs = {}
for col in FEATURE_COLUMNS:
    try:
        auc = roc_auc_score(y, x_feat[col].fillna(0))
        aucs[col] = max(auc, 1 - auc)
    except Exception:
        aucs[col] = 0.5
for feat, auc in sorted(aucs.items(), key=lambda kv: kv[1], reverse=True)[:10]:
    bar = "█" * int((auc - 0.5) * 400)
    print(f"  {feat:25s}: {auc:.4f}  {bar}")

print(f"\nBest AUC: {max(aucs.values()):.4f}")
print(f"Features > 0.52: {sum(1 for a in aucs.values() if a > 0.52)}")
print(f"Features > 0.53: {sum(1 for a in aucs.values() if a > 0.53)}")

x_train, x_val, x_test, y_train, y_val, y_test = _per_symbol_split(x, y)
print(f"\nSplit: train={len(x_train)} val={len(x_val)} test={len(x_test)}")
print(f"Train UP%={y_train.mean():.1%}  Val UP%={y_val.mean():.1%}  Test UP%={y_test.mean():.1%}")

x_tr = x_train.drop(columns=["symbol"], errors="ignore")
x_te = x_test.drop(columns=["symbol"], errors="ignore")
df_b = x_tr.copy(); df_b["__l__"] = y_train.values
mn = df_b["__l__"].value_counts().min()
bal = pd.concat([df_b[df_b["__l__"]==c].sample(mn, random_state=42).sort_index() for c in [0,1]]).sort_index()
xb = bal.drop(columns=["__l__"]); yb = bal["__l__"]

pipe = Pipeline([("sc", StandardScaler()), ("clf", GradientBoostingClassifier(
    n_estimators=100, max_depth=4, learning_rate=0.05, subsample=0.8,
    min_samples_split=30, min_samples_leaf=15, max_features="sqrt", random_state=42))])
print("\nTraining quick model...")
pipe.fit(xb, yb)
proba = pipe.predict_proba(x_te)[:, 1]
model_auc = roc_auc_score(y_test, proba)
print(f"Model ROC-AUC: {model_auc:.4f}  (was 0.4824 before)")
print(f"Proba std: {proba.std():.4f}  (was 0.0411 before — higher = better separation)")
