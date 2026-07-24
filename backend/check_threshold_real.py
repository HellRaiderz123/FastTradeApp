"""
Check what threshold is selected on real val data and inspect proba distribution.
"""
import sys, os
sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", "postgresql://fasttrade:your_new_password@db:5432/fasttrade")

import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.ml.config import StockMLConfig
from app.core.ml.dataset import build_stock_ml_dataset
from app.core.ml.stock_model import _per_symbol_split, _find_best_threshold
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import precision_score, recall_score, f1_score

engine = create_engine(os.environ["DATABASE_URL"])
Session = sessionmaker(bind=engine)
db = Session()

config = StockMLConfig()
from app.db.models_candles import CandleDaily
from sqlalchemy import func

rows = db.query(CandleDaily.symbol, func.count().label("n"))\
         .group_by(CandleDaily.symbol)\
         .having(func.count() >= 500)\
         .order_by(func.count().desc())\
         .limit(30).all()
symbols = [r.symbol for r in rows]
print(f"Using {len(symbols)} symbols")

x, y = build_stock_ml_dataset(db, symbols, config)
print(f"Dataset: {len(x)} rows, label dist: {dict(y.value_counts())}")

x_train, x_val, x_test, y_train, y_val, y_test = _per_symbol_split(x, y)

# Balance train
import pandas as pd
df = x_train.copy(); df["__label__"] = y_train.values
mn = df["__label__"].value_counts().min()
balanced = pd.concat([df[df["__label__"]==c].sample(mn, random_state=42).sort_index() for c in [0,1]]).sort_index()
x_train_b = balanced.drop(columns=["__label__"]); y_train_b = balanced["__label__"]

pipe = Pipeline([("scaler", StandardScaler()), ("clf", GradientBoostingClassifier(
    n_estimators=100, max_depth=4, learning_rate=0.05, subsample=0.8,
    min_samples_split=30, min_samples_leaf=15, max_features="sqrt", random_state=42))])
print("Training (100 estimators for speed)...")
pipe.fit(x_train_b, y_train_b)

y_val_proba = pipe.predict_proba(x_val)[:, 1]
print(f"\nVal proba stats: min={y_val_proba.min():.3f} max={y_val_proba.max():.3f} "
      f"mean={y_val_proba.mean():.3f} p25={np.percentile(y_val_proba,25):.3f} "
      f"p50={np.percentile(y_val_proba,50):.3f} p75={np.percentile(y_val_proba,75):.3f}")
print(f"Val label dist: {dict(pd.Series(y_val.values).value_counts())}")

# Show what each threshold gives
print("\nThreshold sweep on val set:")
print(f"{'t':>5} {'pred%':>7} {'prec':>7} {'recall':>7} {'geo':>7} {'valid':>6}")
for t in np.arange(0.35, 0.71, 0.02):
    preds = (y_val_proba >= t).astype(int)
    rate = preds.mean()
    p = precision_score(y_val.values, preds, zero_division=0)
    r = recall_score(y_val.values, preds, zero_division=0)
    geo = (p*r)**0.5 if p>0 and r>0 else 0
    valid = "✓" if 0.20 <= rate <= 0.70 else "✗"
    print(f"{t:>5.2f} {rate:>7.1%} {p:>7.1%} {r:>7.1%} {geo:>7.4f} {valid:>6}")

best_t = _find_best_threshold(y_val.values, y_val_proba)
print(f"\nSelected threshold: {best_t}")

y_test_proba = pipe.predict_proba(x_test)[:, 1]
y_pred = (y_test_proba >= best_t).astype(int)
print(f"Test  → prec={precision_score(y_test,y_pred,zero_division=0):.2%}  "
      f"recall={recall_score(y_test,y_pred,zero_division=0):.2%}  "
      f"f1={f1_score(y_test,y_pred,zero_division=0):.2%}  "
      f"pred_rate={y_pred.mean():.1%}")
