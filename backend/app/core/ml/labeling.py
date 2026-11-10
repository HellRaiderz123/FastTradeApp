"""
Triple Barrier Labeling — Lopez de Prado, "Advances in Financial Machine Learning", Ch.3.

Three-class output:
  BULLISH  ( 1) — TP barrier hit first within horizon
  BEARISH  (-1) — SL barrier hit first within horizon
  NEUTRAL  ( 0) — neither barrier hit (time barrier only)

Time-barrier rows (NEUTRAL) are kept for training so the model learns
"no edge" setups, but they are clearly separated from directional labels.

Overlap / leakage fix:
  After labeling, stride-sample every `horizon` bars per symbol so that
  no two training rows share future price data in their label windows.
"""

import logging
import numpy as np
import pandas as pd
from app.core.ml.config import StockMLConfig

logger = logging.getLogger(__name__)


def _compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"]  - df["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def add_future_return_labels(df: pd.DataFrame, config: StockMLConfig) -> pd.DataFrame:
    """
    Triple Barrier Label — three-class, overlap-free.

    For each bar t:
      upper = close[t] * (1 + tp_mult * ATR%[t])
      lower = close[t] * (1 - sl_mult * ATR%[t])
      Scan forward up to `horizon` bars.

    Label:
       1  (BULLISH) — upper hit first
      -1  (BEARISH) — lower hit first
       0  (NEUTRAL) — time barrier (neither hit)

    Overlap fix: stride-sample every `horizon` rows so label windows
    never share future bars.  This reduces dataset size but eliminates
    the ~95% label-window overlap that was poisoning training.
    """
    data = df.copy().reset_index(drop=True)

    tp_mult = float(getattr(config, "tp_atr_mult", 1.5))
    sl_mult = float(getattr(config, "sl_atr_mult", 1.0))
    horizon = int(config.horizon)

    atr    = _compute_atr(data, period=14)
    atr_pct = (atr / data["close"]).values

    n      = len(data)
    closes = data["close"].values
    highs  = data["high"].values
    lows   = data["low"].values

    raw_labels = np.zeros(n, dtype=np.int8)   # default: NEUTRAL
    has_atr    = np.zeros(n, dtype=bool)

    for i in range(n - 1):
        atr_i = atr_pct[i]
        if np.isnan(atr_i) or atr_i <= 0:
            continue
        has_atr[i] = True

        entry = closes[i]
        upper = entry * (1.0 + tp_mult * atr_i)
        lower = entry * (1.0 - sl_mult * atr_i)

        end = min(i + horizon + 1, n)
        fh  = highs[i + 1:end]
        fl  = lows[i + 1:end]
        if len(fh) == 0:
            continue

        tp_mask = fh >= upper
        sl_mask = fl <= lower
        tp_hit  = tp_mask.any()
        sl_hit  = sl_mask.any()

        if tp_hit and sl_hit:
            raw_labels[i] = 1 if np.argmax(tp_mask) <= np.argmax(sl_mask) else -1
        elif tp_hit:
            raw_labels[i] = 1
        elif sl_hit:
            raw_labels[i] = -1
        # else: 0 (NEUTRAL / time barrier)

    data["_raw_label"] = raw_labels
    data["_has_atr"]   = has_atr

    # Drop rows where ATR was not yet available (first ~14 bars)
    data = data[data["_has_atr"]].drop(columns=["_has_atr"]).copy()
    data = data.reset_index(drop=True)

    # -----------------------------------------------------------------------
    # Stride sampling — keep every `horizon`-th row so label windows
    # do not overlap.  We stride from the END of each symbol's data so
    # the most recent (test-set) rows are always included.
    # -----------------------------------------------------------------------
    stride_idx = list(range(len(data) - 1, -1, -horizon))
    stride_idx = sorted(stride_idx)
    data = data.iloc[stride_idx].copy().reset_index(drop=True)

    # Final label column: keep three classes
    data["label"] = data["_raw_label"].astype(int)
    data = data.drop(columns=["_raw_label"])

    counts = data["label"].value_counts().to_dict()
    total  = len(data)
    logger.info(
        f"Triple Barrier (3-class, strided): "
        f"BULLISH={counts.get(1,0)/total:.2%}, "
        f"NEUTRAL={counts.get(0,0)/total:.2%}, "
        f"BEARISH={counts.get(-1,0)/total:.2%}, "
        f"rows={total}, tp={tp_mult}xATR, sl={sl_mult}xATR, horizon={horizon}"
    )
    return data
