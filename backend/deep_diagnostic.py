"""
Deep diagnostic: why is the model at chance level?
Checks: label distribution, feature-label correlation, ROC-AUC per feature,
and whether ANY single feature beats 50% AUC.
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

# Use ALL available symbols (not just 30)
rows = db.query(CandleDaily.symbol, func.count().label("n"))\
         .group_by(CandleDaily.symbol).having(func.count() >= 500)\
         .order_by(func.count().desc()).all()
symbols = [r.symbol for r in rows]
print(f"Using {len(symbols)} symbols")

x, y = build_stock_ml_dataset(db, symbols, config)
print(f"\nDataset: {len(x)} rows")
print(f"Label dist: {dict(y.value_counts())}  ({y.mean():.1%} UP)")

x_feat = x.drop(columns=["symbol"], errors="ignore")

# --- 1. Feature-label correlation ---
print("\n--- Feature-label Pearson correlation (top 10 by abs) ---")
corrs = x_feat.corrwith(y).abs().sort_values(ascending=False)
for feat, c in corrs.head(10).items():
    print(f"  {feat:25s}: {c:.4f}")

# --- 2. Per-feature ROC-AUC ---
print("\n--- Per-feature ROC-AUC (top 10, >0.50 = useful) ---")
aucs = {}
for col in FEATURE_COLUMNS:
    try:
        auc = roc_auc_score(y, x_feat[col].fillna(0))
        aucs[col] = max(auc, 1 - auc)  # flip if inverted
    except Exception:
        aucs[col] = 0.5
aucs_sorted = sorted(aucs.items(), key=lambda kv: kv[1], reverse=True)
for feat, auc in aucs_sorted[:10]:
    bar = "█" * int((auc - 0.5) * 200)
    print(f"  {feat:25s}: {auc:.4f}  {bar}")

best_auc = aucs_sorted[0][1]
print(f"\nBest single-feature AUC: {best_auc:.4f}")
print(f"Features > 0.52 AUC: {sum(1 for _, a in aucs_sorted if a > 0.52)}")

# --- 3. Train/test split stats ---
x_train, x_val, x_test, y_train, y_val, y_test = _per_symbol_split(x, y)
print(f"\nSplit sizes: train={len(x_train)} val={len(x_val)} test={len(x_test)}")
print(f"Train label: {y_train.mean():.1%} UP  |  Test label: {y_test.mean():.1%} UP")

# --- 4. Quick model ROC-AUC on test ---
x_tr = x_train.drop(columns=["symbol"], errors="ignore")
x_te = x_test.drop(columns=["symbol"], errors="ignore")
df_b = x_tr.copy(); df_b["__l__"] = y_train.values
mn = df_b["__l__"].value_counts().min()
bal = pd.concat([df_b[df_b["__l__"]==c].sample(mn, random_state=42).sort_index() for c in [0,1]]).sort_index()
xb = bal.drop(columns=["__l__"]); yb = bal["__l__"]

pipe = Pipeline([("sc", StandardScaler()), ("clf", GradientBoostingClassifier(
    n_estimators=100, max_depth=4, learning_rate=0.05, subsample=0.8,
    min_samples_split=30, min_samples_leaf=15, max_features="sqrt", random_state=42))])
print("\nTraining quick model (100 est)...")
pipe.fit(xb, yb)
proba = pipe.predict_proba(x_te)[:, 1]
model_auc = roc_auc_score(y_test, proba)
print(f"Model ROC-AUC on test: {model_auc:.4f}")
print(f"Proba range: min={proba.min():.3f} max={proba.max():.3f} std={proba.std():.4f}")

# --- 5. Label leakage check: does test period have different UP% than train? ---
print(f"\nLabel leakage / regime check:")
print(f"  Train UP%: {y_train.mean():.1%}")
print(f"  Val   UP%: {y_val.mean():.1%}")
print(f"  Test  UP%: {y_test.mean():.1%}")
