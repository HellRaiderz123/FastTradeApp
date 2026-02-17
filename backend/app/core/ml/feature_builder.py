from typing import List
import numpy as np
import pandas as pd

from app.core.signals.ta_engine import compute_rsi, compute_macd, compute_adx
from app.core.ml.config import StockMLConfig


FEATURE_COLUMNS: List[str] = [
    # Price returns (momentum)
    "ret_1",
    "ret_short",
    "ret_long",
    # Volatility
    "volatility",
    "atr_norm",
    # Trend indicators
    "rsi",
    "macd_hist",
    "adx",
    # Moving averages
    "ema_fast",
    "ema_slow",
    "ema_long",
    "ema_fast_slope",
    "ema_slow_slope",
    # EMA relative position
    "price_vs_ema_fast",
    "price_vs_ema_slow",
    "ema_cross",
    # Bollinger Bands
    "bb_width",
    "bb_position",
    # Volume
    "volume_ratio",
    "obv_slope",
    # Candle patterns
    "body_ratio",
    "upper_shadow",
    "lower_shadow",
]


def build_features_from_df(df: pd.DataFrame, config: StockMLConfig) -> pd.DataFrame:
    """Build ML features from OHLCV dataframe."""
    if df.empty:
        return df

    data = df.copy()
    
    # --- Price Returns (Momentum) ---
    data["ret_1"] = data["close"].pct_change()
    data["ret_short"] = data["close"].pct_change(config.ret_short_window)
    data["ret_long"] = data["close"].pct_change(config.ret_long_window)

    # --- Volatility ---
    data["volatility"] = data["close"].pct_change().rolling(config.vol_window).std()
    
    # ATR normalized by close price (position-independent)
    tr = pd.concat([
        data["high"] - data["low"],
        (data["high"] - data["close"].shift(1)).abs(),
        (data["low"] - data["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    data["atr_norm"] = tr.rolling(14).mean() / data["close"]

    # --- Trend Indicators ---
    data["rsi"] = compute_rsi(data["close"], period=config.rsi_period)
    _, _, macd_hist = compute_macd(data["close"])
    data["macd_hist"] = macd_hist

    data["adx"] = compute_adx(data)

    # --- Moving Averages ---
    data["ema_fast"] = data["close"].ewm(span=config.ema_fast).mean()
    data["ema_slow"] = data["close"].ewm(span=config.ema_slow).mean()
    data["ema_long"] = data["close"].ewm(span=config.ema_long).mean()

    data["ema_fast_slope"] = data["ema_fast"].pct_change(5)  # 5-day slope of EMA
    data["ema_slow_slope"] = data["ema_slow"].pct_change(5)
    
    # --- EMA Relative Position (price-relative, not absolute) ---
    data["price_vs_ema_fast"] = (data["close"] - data["ema_fast"]) / data["ema_fast"]
    data["price_vs_ema_slow"] = (data["close"] - data["ema_slow"]) / data["ema_slow"]
    data["ema_cross"] = (data["ema_fast"] - data["ema_slow"]) / data["ema_slow"]
    
    # --- Bollinger Bands ---
    bb_mid = data["close"].rolling(20).mean()
    bb_std = data["close"].rolling(20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    data["bb_width"] = (bb_upper - bb_lower) / bb_mid  # Normalized width
    data["bb_position"] = (data["close"] - bb_lower) / (bb_upper - bb_lower)  # 0-1 position within bands

    # --- Volume ---
    data["volume_ma"] = data["volume"].rolling(config.vol_window).mean()
    data["volume_ratio"] = data["volume"] / data["volume_ma"]
    
    # OBV slope (On Balance Volume momentum)
    obv = ((data["close"] > data["close"].shift(1)).astype(int) * 2 - 1) * data["volume"]
    obv_cumsum = obv.cumsum()
    data["obv_slope"] = obv_cumsum.pct_change(10)  # 10-day OBV momentum
    
    # --- Candle Body Patterns ---
    candle_range = data["high"] - data["low"]
    candle_range = candle_range.replace(0, np.nan)  # Avoid division by zero
    data["body_ratio"] = (data["close"] - data["open"]) / candle_range  # -1 to +1
    data["upper_shadow"] = (data["high"] - data[["open", "close"]].max(axis=1)) / candle_range
    data["lower_shadow"] = (data[["open", "close"]].min(axis=1) - data["low"]) / candle_range

    if float(data["volume"].fillna(0).sum()) == 0.0:
        data["volume_ratio"] = 1.0
        data["obv_slope"] = 0.0

    data = data.replace([np.inf, -np.inf], np.nan).dropna()
    return data
