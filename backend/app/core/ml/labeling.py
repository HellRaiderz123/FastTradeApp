"""
Triple Barrier Labeling — Lopez de Prado, "Advances in Financial Machine Learning", Ch.3.

Label = 1  if price hits +tp_atr * ATR(14) first  (profit target touched)
Label = 0  if price hits -sl_atr * ATR(14) first  (stop loss touched)
Label = -1 if neither barrier hit within `horizon` days (time barrier — no trade)

Why this beats fixed forward-return labels:
- Volatility-adjusted: a 4% move on RELIANCE vs a small-cap are treated differently
- Asymmetric: captures actual trade outcomes, not just closing price
- Removes the "label noise" that makes models predict random noise

For binary classification we map: 1 → 1 (BUY), 0 or -1 → 0 (NO_BUY).
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
        (df["low"] - df["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def add_future_return_labels(df: pd.DataFrame, config: StockMLConfig) -> pd.DataFrame:
    """
    Triple Barrier Label (Lopez de Prado Ch.3) — vectorized implementation.

    For each bar t:
      - Upper barrier = close[t] * (1 + tp_mult * atr_pct[t])
      - Lower barrier = close[t] * (1 - sl_mult * atr_pct[t])
      - Scan forward up to `horizon` bars using numpy (no Python loop over bars)
      - Label = 1 if upper hit first, 0 if lower hit first, -1 if time barrier

    Binary output: label=1 (BUY) only when upper barrier hit first.
    """
    data = df.copy().reset_index(drop=True)

    tp_mult = getattr(config, "tp_atr_mult", 2.0)
    sl_mult = getattr(config, "sl_atr_mult", 1.0)
    horizon = config.horizon

    atr = _compute_atr(data, period=14)
    atr_pct = (atr / data["close"]).values

    n = len(data)
    closes = data["close"].values
    highs = data["high"].values
    lows = data["low"].values

    labels = np.full(n, -1, dtype=np.int8)  # default: time barrier
    valid = np.zeros(n, dtype=bool)

    for i in range(n - 1):
        atr_i = atr_pct[i]
        if np.isnan(atr_i) or atr_i <= 0:
            continue

        entry = closes[i]
        upper = entry * (1.0 + tp_mult * atr_i)
        lower = entry * (1.0 - sl_mult * atr_i)

        end = min(i + horizon + 1, n)
        fh = highs[i + 1:end]   # future highs slice
        fl = lows[i + 1:end]    # future lows slice

        if len(fh) == 0:
            continue

        tp_mask = fh >= upper
        sl_mask = fl <= lower

        tp_touched = tp_mask.any()
        sl_touched = sl_mask.any()

        if tp_touched and sl_touched:
            tp_idx = np.argmax(tp_mask)
            sl_idx = np.argmax(sl_mask)
            labels[i] = 1 if tp_idx <= sl_idx else 0
        elif tp_touched:
            labels[i] = 1
        elif sl_touched:
            labels[i] = 0
        # else: -1 (time barrier, already set)

        valid[i] = True

    data["_triple_label"] = labels
    data["_valid"] = valid
    data = data[data["_valid"]].drop(columns=["_valid"]).copy()

    # Binary: 1 = profit target hit (BUY), 0 = stop hit or time barrier (NO_BUY)
    data["label"] = (data["_triple_label"] == 1).astype(int)
    data = data.drop(columns=["_triple_label"])

    buy_rate = data["label"].mean()
    logger.info(
        f"Triple Barrier labels: buy_rate={buy_rate:.3f}, "
        f"tp={tp_mult}x ATR, sl={sl_mult}x ATR, horizon={horizon}, rows={len(data)}"
    )

    return data
