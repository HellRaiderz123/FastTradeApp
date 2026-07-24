"""
ML Pipeline Diagnostic Script
Run from backend/ directory:
    python test_ml_pipeline.py

Tests every layer without needing to rebuild Docker:
  1. DB connection + data availability
  2. Feature building (NaN/inf checks, column presence)
  3. Labeling (class balance, neutral-zone removal)
  4. Train/val/test split (size, balance per split)
  5. Model training (fits without error)
  6. Threshold calibration (not degenerate)
  7. Final metrics (precision/recall balance check)
  8. Prediction sanity (single symbol inference)
"""

import sys
import os
from pathlib import Path

# ── path setup so imports work from backend/ ──────────────────────────────────
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Load .env manually (no python-dotenv needed)
env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

import numpy as np
import pandas as pd
import traceback

PASS = "✓"
FAIL = "✗"
WARN = "⚠"
SEP  = "─" * 60


def section(title: str):
    print(f"\n{SEP}\n  {title}\n{SEP}")


def check(label: str, ok: bool, detail: str = ""):
    icon = PASS if ok else FAIL
    msg = f"  {icon}  {label}"
    if detail:
        msg += f"  →  {detail}"
    print(msg)
    return ok


# ══════════════════════════════════════════════════════════════════════════════
# 1. DB CONNECTION
# ══════════════════════════════════════════════════════════════════════════════
section("1. Database Connection")
try:
    from app.db.session import SessionLocal
    from app.db.models_candles import CandleDaily
    from sqlalchemy import func

    db = SessionLocal()
    total = db.query(func.count(CandleDaily.id)).scalar()
    symbols_q = db.query(CandleDaily.symbol, func.count(CandleDaily.id).label("cnt")) \
                  .group_by(CandleDaily.symbol) \
                  .order_by(func.count(CandleDaily.id).desc()) \
                  .all()
    symbols_500 = [s for s, c in symbols_q if c >= 500]

    check("DB connected", True)
    check("Total daily candles", total > 0, f"{total:,}")
    check("Symbols with 500+ days", len(symbols_500) > 0, f"{len(symbols_500)} symbols")

    if not symbols_500:
        print(f"\n  {FAIL}  No symbols with 500+ days — run Backfill first. Exiting.")
        sys.exit(1)

    # Pick top 30 symbols for realistic test (more = better signal on ROC-AUC)
    TEST_SYMBOLS = [s for s, _ in symbols_q[:30]]
    print(f"\n  Using symbols for test: {TEST_SYMBOLS}")

except Exception as e:
    print(f"  {FAIL}  DB connection failed: {e}")
    traceback.print_exc()
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# 2. RAW CANDLE LOAD
# ══════════════════════════════════════════════════════════════════════════════
section("2. Raw Candle Load")
try:
    from app.core.ml.dataset import _load_candles_df
    from app.core.ml.config import StockMLConfig

    config = StockMLConfig()
    sym = TEST_SYMBOLS[0]
    raw = _load_candles_df(db, sym, config.timeframe, config.max_candles)

    check("Candles loaded", not raw.empty, f"{len(raw)} rows for {sym}")
    check("Required columns present",
          all(c in raw.columns for c in ["open", "high", "low", "close", "volume"]))
    check("No NaN in OHLCV", raw[["open","high","low","close","volume"]].isna().sum().sum() == 0,
          f"{raw[['open','high','low','close','volume']].isna().sum().sum()} NaNs")
    check("Chronological order",
          raw["timestamp"].is_monotonic_increasing,
          f"first={raw['timestamp'].iloc[0]}  last={raw['timestamp'].iloc[-1]}")

except Exception as e:
    print(f"  {FAIL}  Candle load failed: {e}")
    traceback.print_exc()


# ══════════════════════════════════════════════════════════════════════════════
# 3. FEATURE BUILDING
# ══════════════════════════════════════════════════════════════════════════════
section("3. Feature Building")
try:
    from app.core.ml.feature_builder import build_features_from_df, FEATURE_COLUMNS

    features = build_features_from_df(raw, config)
    check("Features built", not features.empty, f"{len(features)} rows")
    check("All feature columns present",
          all(c in features.columns for c in FEATURE_COLUMNS),
          f"missing: {[c for c in FEATURE_COLUMNS if c not in features.columns]}")

    nan_counts = features[FEATURE_COLUMNS].isna().sum()
    inf_counts = features[FEATURE_COLUMNS].isin([np.inf, -np.inf]).sum()
    check("No NaN in features", nan_counts.sum() == 0,
          f"{nan_counts[nan_counts>0].to_dict()}" if nan_counts.sum() > 0 else "clean")
    check("No Inf in features", inf_counts.sum() == 0,
          f"{inf_counts[inf_counts>0].to_dict()}" if inf_counts.sum() > 0 else "clean")

    print(f"\n  Feature stats (first symbol):")
    stats = features[FEATURE_COLUMNS].describe().loc[["mean","std","min","max"]]
    for col in FEATURE_COLUMNS:
        mn, sd, lo, hi = stats[col]["mean"], stats[col]["std"], stats[col]["min"], stats[col]["max"]
        flag = f"  {WARN} large range" if (hi - lo) > 1000 else ""
        print(f"    {col:<22} mean={mn:+.4f}  std={sd:.4f}  [{lo:.4f}, {hi:.4f}]{flag}")

except Exception as e:
    print(f"  {FAIL}  Feature building failed: {e}")
    traceback.print_exc()


# ══════════════════════════════════════════════════════════════════════════════
# 4. LABELING
# ══════════════════════════════════════════════════════════════════════════════
section("4. Labeling")
try:
    from app.core.ml.labeling import add_future_return_labels

    labeled = add_future_return_labels(features, config)
    check("Labels created", not labeled.empty, f"{len(labeled)} rows after neutral-zone removal")

    n_up   = (labeled["label"] == 1).sum()
    n_down = (labeled["label"] == 0).sum()
    ratio  = n_up / max(n_down, 1)
    check("Label column exists", "label" in labeled.columns)
    check("Only 0/1 labels", labeled["label"].isin([0, 1]).all())
    check("No NaN labels", labeled["label"].isna().sum() == 0)
    check("Class balance reasonable (0.5–2.0 ratio)",
          0.5 <= ratio <= 2.0,
          f"UP={n_up}  DOWN={n_down}  ratio={ratio:.3f}")

    dropped_pct = (1 - len(labeled) / len(features)) * 100
    print(f"\n  Neutral zone removed: {dropped_pct:.1f}% of rows dropped")
    print(f"  Horizon={config.horizon}d  threshold={config.return_threshold*100:.1f}%")

except Exception as e:
    print(f"  {FAIL}  Labeling failed: {e}")
    traceback.print_exc()


# ══════════════════════════════════════════════════════════════════════════════
# 5. FULL DATASET BUILD (all test symbols)
# ══════════════════════════════════════════════════════════════════════════════
section("5. Full Dataset Build")
try:
    from app.core.ml.dataset import build_stock_ml_dataset

    x, y = build_stock_ml_dataset(db, TEST_SYMBOLS, config)
    check("Dataset built", not x.empty, f"{len(x)} rows  {len(TEST_SYMBOLS)} symbols")
    check("symbol column present", "symbol" in x.columns)
    check("Feature columns present",
          all(c in x.columns for c in FEATURE_COLUMNS))
    check("y length matches x", len(x) == len(y))
    check("y has only 0/1", y.isin([0, 1]).all())

    vc = y.value_counts()
    print(f"\n  Class distribution: UP={vc.get(1,0)}  DOWN={vc.get(0,0)}")

except Exception as e:
    print(f"  {FAIL}  Dataset build failed: {e}")
    traceback.print_exc()
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# 6. TRAIN / VAL / TEST SPLIT
# ══════════════════════════════════════════════════════════════════════════════
section("6. Train / Val / Test Split")
try:
    from app.core.ml.stock_model import _per_symbol_split

    x_train, x_val, x_test, y_train, y_val, y_test = _per_symbol_split(x, y)

    total = len(x)
    check("Train size ~70%", 0.60 <= len(x_train)/total <= 0.80,
          f"{len(x_train)} ({len(x_train)/total*100:.1f}%)")
    check("Val size ~10%",   0.05 <= len(x_val)/total   <= 0.20,
          f"{len(x_val)} ({len(x_val)/total*100:.1f}%)")
    check("Test size ~20%",  0.10 <= len(x_test)/total  <= 0.30,
          f"{len(x_test)} ({len(x_test)/total*100:.1f}%)")
    check("No symbol column in splits",
          "symbol" not in x_train.columns and "symbol" not in x_test.columns)
    check("No NaN in x_train", x_train.isna().sum().sum() == 0)
    check("No NaN in x_test",  x_test.isna().sum().sum() == 0)

    for name, yy in [("train", y_train), ("val", y_val), ("test", y_test)]:
        vc = yy.value_counts()
        r  = vc.get(1, 0) / max(vc.get(0, 1), 1)
        ok = 0.4 <= r <= 2.5
        check(f"  {name} class balance", ok,
              f"UP={vc.get(1,0)}  DOWN={vc.get(0,0)}  ratio={r:.3f}")

except Exception as e:
    print(f"  {FAIL}  Split failed: {e}")
    traceback.print_exc()
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# 7. FULL TRAIN via train_stock_model (tests the real code path)
# ══════════════════════════════════════════════════════════════════════════════
section("7. Full Train via train_stock_model")
try:
    from app.core.ml.stock_model import train_stock_model
    from app.core.ml.config import StockMLConfig

    result = train_stock_model(db, TEST_SYMBOLS, config)

    accuracy  = result["accuracy"]
    precision = result["precision"]
    recall    = result["recall"]
    f1        = result["f1_score"]
    roc_auc   = result.get("roc_auc", 0.0)
    best_t    = result["decision_threshold"]

    check("train_stock_model ran without error", True)
    print(f"\n  train={result['train_rows']}  val={result.get('val_rows','?')}  test={result['test_rows']}")
    print(f"  decision_threshold={best_t}")
    print()

except Exception as e:
    print(f"  {FAIL}  train_stock_model failed: {e}")
    traceback.print_exc()
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# 8. THRESHOLD CHECK (from saved result)
# ══════════════════════════════════════════════════════════════════════════════
section("8. Threshold Check")
try:
    check("Threshold in [0.35, 0.70]", 0.35 <= best_t <= 0.70, f"threshold={best_t}")
except Exception as e:
    print(f"  {FAIL}  {e}")


# ══════════════════════════════════════════════════════════════════════════════
# 9. FINAL TEST METRICS
# ══════════════════════════════════════════════════════════════════════════════
section("9. Final Test Metrics")
try:
    print(f"  Threshold : {best_t}")
    print()
    check("Accuracy  > 50%",   accuracy  > 0.50, f"{accuracy*100:.2f}%")
    check("Precision > 50%",   precision > 0.50, f"{precision*100:.2f}%")
    check("Recall    > 50%",   recall    > 0.50, f"{recall*100:.2f}%")
    check("F1        > 50%",   f1        > 0.50, f"{f1*100:.2f}%")
    check("ROC-AUC   > 0.52",  roc_auc   > 0.52, f"{roc_auc:.4f}")

    pr_ratio = precision / max(recall, 1e-6)
    check("Precision/Recall balanced (0.5–2.0)",
          0.5 <= pr_ratio <= 2.0,
          f"ratio={pr_ratio:.3f}")

    if recall > 0.90:
        print(f"\n  {WARN}  Recall={recall:.3f} suspiciously high — model may predict all UP.")
    if precision < 0.45:
        print(f"\n  {WARN}  Precision={precision:.3f} low — too many false positives.")
    if roc_auc < 0.50:
        print(f"\n  {WARN}  ROC-AUC={roc_auc:.4f} below 0.5 — model is anti-predictive.")
        print(f"       The model's raw probabilities are biased. Check class balance in training.")

except Exception as e:
    print(f"  {FAIL}  Metrics check failed: {e}")
    traceback.print_exc()


# ══════════════════════════════════════════════════════════════════════════════
# 10. FEATURE IMPORTANCE (from saved metadata)
# ══════════════════════════════════════════════════════════════════════════════
section("10. Feature Importance")
try:
    fi = result.get("feature_importance", {})
    if fi:
        top = sorted(fi.items(), key=lambda x: x[1], reverse=True)
        print("  Top 10 features:")
        for feat, imp in top[:10]:
            bar = "█" * int(imp * 200)
            print(f"    {feat:<22} {imp:.4f}  {bar}")
        top_imp = top[0][1]
        check("No single feature dominates (< 40%)", top_imp < 0.40,
              f"top={top[0][0]} at {top_imp*100:.1f}%")
    else:
        print(f"  {WARN}  No feature importance in result")
except Exception as e:
    print(f"  {FAIL}  {e}")


# ══════════════════════════════════════════════════════════════════════════════
# 11. SINGLE SYMBOL PREDICTION SANITY
# ══════════════════════════════════════════════════════════════════════════════
section("11. Single Symbol Prediction Sanity")
try:
    from app.core.ml.stock_model import predict_stock_signal

    pred = predict_stock_signal(db, TEST_SYMBOLS[0], config)
    check("predict_stock_signal ran", True)
    check("signal is valid", pred["signal"] in ["BULLISH", "BEARISH", "NO_TRADE"],
          pred["signal"])
    check("confidence in [0,100]", 0 <= pred["confidence"] <= 100,
          str(pred["confidence"]))
    print(f"\n  Symbol    : {TEST_SYMBOLS[0]}")
    print(f"  Signal    : {pred['signal']}")
    print(f"  Confidence: {pred['confidence']}")
    print(f"  Reason    : {pred['reason']}")
except Exception as e:
    print(f"  {FAIL}  Prediction failed: {e}")
    traceback.print_exc()


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
section("SUMMARY")
print(f"""
  Dataset  : {result['total_samples']} rows  |  {len(TEST_SYMBOLS)} symbols
  Split    : train={result['train_rows']}  val={result.get('val_rows','?')}  test={result['test_rows']}
  Threshold: {best_t}
  Accuracy : {accuracy*100:.2f}%
  Precision: {precision*100:.2f}%
  Recall   : {recall*100:.2f}%
  F1       : {f1*100:.2f}%
  ROC-AUC  : {roc_auc:.4f}

  NOTE: This used only {len(TEST_SYMBOLS)} symbols.
  Full training uses all 178 symbols + 200 estimators — metrics will differ.
""")

db.close()
