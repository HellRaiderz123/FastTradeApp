from typing import List
import numpy as np
import pandas as pd

from app.core.signals.ta_engine import compute_rsi, compute_macd, compute_adx
from app.core.ml.config import StockMLConfig


FEATURE_COLUMNS: List[str] = [
    "ret_1",
    "ret_short",
    "ret_long",
    "volatility",
    "rsi",
    "macd_hist",
    "adx",
    "ema_fast",
    "ema_slow",
    "ema_long",
    "ema_fast_slope",
    "ema_slow_slope",
    "volume_ratio",
]


def build_features_from_df(df: pd.DataFrame, config: StockMLConfig) -> pd.DataFrame:
    """Build ML features from OHLCV dataframe."""
    if df.empty:
        return df

    data = df.copy()
    data["ret_1"] = data["close"].pct_change()
    data["ret_short"] = data["close"].pct_change(config.ret_short_window)
    data["ret_long"] = data["close"].pct_change(config.ret_long_window)

    data["volatility"] = data["close"].pct_change().rolling(config.vol_window).std()

    data["rsi"] = compute_rsi(data["close"], period=config.rsi_period)
    _, _, macd_hist = compute_macd(data["close"])
    data["macd_hist"] = macd_hist

    data["adx"] = compute_adx(data)

    data["ema_fast"] = data["close"].ewm(span=config.ema_fast).mean()
    data["ema_slow"] = data["close"].ewm(span=config.ema_slow).mean()
    data["ema_long"] = data["close"].ewm(span=config.ema_long).mean()

    data["ema_fast_slope"] = data["ema_fast"].diff()
    data["ema_slow_slope"] = data["ema_slow"].diff()

    data["volume_ma"] = data["volume"].rolling(config.vol_window).mean()
    data["volume_ratio"] = data["volume"] / data["volume_ma"]

    if float(data["volume"].fillna(0).sum()) == 0.0:
        data["volume_ratio"] = 1.0

    data = data.replace([np.inf, -np.inf], np.nan).dropna()
    return data
