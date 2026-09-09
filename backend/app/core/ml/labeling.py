import pandas as pd
import numpy as np
from app.core.ml.config import StockMLConfig

def add_future_return_labels(df: pd.DataFrame, config: StockMLConfig) -> pd.DataFrame:
    """
    Label rows based on forward return over horizon.
    PRESERVES ALL ROWS to maintain chronological continuity for LSTM sequences.
    """
    data = df.copy()

    future_close = data["close"].shift(-config.horizon)
    data["_future_return"] = (future_close / data["close"]) - 1.0

    data = data.dropna(subset=["_future_return"]).copy()

    # Adaptive threshold: max(config.return_threshold, 1.5x rolling vol)
    rolling_vol = data["close"].pct_change().rolling(20).std().shift(1).fillna(config.return_threshold)
    adaptive_threshold = (rolling_vol * 1.5).clip(lower=config.return_threshold, upper=0.06)
    data["label"] = (data["_future_return"] > adaptive_threshold).astype(int)

    # Enforce BUY rate in 25-45% range for balanced, high-precision labels
    buy_rate = data["label"].mean()
    if buy_rate > 0.45:
        # Too many BUYs — raise threshold to the Nth percentile of future returns
        target_pct = 100 * (1 - 0.40)  # target ~40% BUY rate
        cutoff = np.percentile(data["_future_return"], target_pct)
        data["label"] = (data["_future_return"] > max(cutoff, config.return_threshold)).astype(int)
    elif buy_rate < 0.25:
        # Too few BUYs — lower to 25th percentile of positive returns
        pos = data["_future_return"][data["_future_return"] > 0]
        if len(pos) > 0:
            cutoff = np.percentile(pos, 25)
            data["label"] = (data["_future_return"] > cutoff).astype(int)

    data = data.drop(columns=["_future_return"])
    return data