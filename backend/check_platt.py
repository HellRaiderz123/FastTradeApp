"""
Verify Platt scaling stretches compressed probabilities and improves threshold selection.
"""
import sys, os
sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", "postgresql://fasttrade:your_new_password@db:5432/fasttrade")

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import precision_score, recall_score, f1_score

from app.core.ml.config import StockMLConfig
from app.core.ml.dataset import build_stock_ml_dataset
from app.core.ml.stock_model import _per_symbol_split, _find_best_threshold
from app.db.models_candles import CandleDaily

engine = create_engine(os.environ["DATABASE_URL"])
db = sessionmaker(bind=engine)()
config = StockMLConfig()

rows = db.query(CandleDaily.symbol, func.count().label("n"))\
         .group_by(CandleDaily.symbol).having(func.count() >= 500)\
         .order_by(func.count().desc()).limit(30).all()
symbols = [r.symbol for r in rows]

x, y = build_stock_ml_dataset(db, symbols, config)
x_train, x_val, x_test, y_train, y_val, y_test = _per_symbol_split(x, y)

df = x_train.copy(); df["__label__"] = y_train.values
mn = df["__label__"].value_counts().min()
balanced = pd.concat([df[df["__label__"]==c].sample(mn, random_state=42).sort_index() for c in [0,1]]).sort_index()
x_train_b = balanced.drop(columns=["__label__"]); y_train_b = balanced["__label__"]

pipe = Pipeline([("scaler", StandardScaler()), ("clf", GradientBoostingClassifier(
    n_estimators=100, max_depth=4, learning_rate=0.05, subsample=0.8,
    min_samples_split=30, min_samples_leaf=15, max_features="sqrt", random_state=42))])
print("Training...")
pipe.fit(x_train_b, y_train_b)

# Raw probabilities
raw_proba = pipe.predict_proba(x_val)[:, 1]
print(f"\nRaw proba   : min={raw_proba.min():.3f} max={raw_proba.max():.3f} "
      f"mean={raw_proba.mean():.3f} std={raw_proba.std():.3f}")

# Platt-calibrated
cal = CalibratedClassifierCV(pipe, cv="prefit", method="sigmoid")
cal.fit(x_val, y_val)
cal_proba = cal.predict_proba(x_val)[:, 1]
print(f"Platt proba : min={cal_proba.min():.3f} max={cal_proba.max():.3f} "
      f"mean={cal_proba.mean():.3f} std={cal_proba.std():.3f}")

raw_t = _find_best_threshold(y_val.values, raw_proba)
cal_t = _find_best_threshold(y_val.values, cal_proba)
print(f"\nRaw threshold: {raw_t}  |  Platt threshold: {cal_t}")

# Test set comparison
raw_test = pipe.predict_proba(x_test)[:, 1]
cal_test = cal.predict_proba(x_test)[:, 1]

for label, proba, t in [("Raw  ", raw_test, raw_t), ("Platt", cal_test, cal_t)]:
    pred = (proba >= t).astype(int)
    p = precision_score(y_test, pred, zero_division=0)
    r = recall_score(y_test, pred, zero_division=0)
    f = f1_score(y_test, pred, zero_division=0)
    acc = (pred == y_test.values).mean()
    print(f"{label} → acc={acc:.2%}  prec={p:.2%}  recall={r:.2%}  f1={f:.2%}  pred_rate={pred.mean():.1%}")
