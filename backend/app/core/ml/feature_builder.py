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
    # Lag features (autocorrelation)
    "ret_1_lag1",
    "ret_1_lag2",
    "ret_1_lag3",
    # Volatility
    "volatility",
    "atr_norm",
    "volatility_change",
    # Trend indicators
    "rsi",
    "rsi_normalized",
    "macd_hist",
    "macd_hist_change",
    "adx",
    # EMA slopes (price-relative, not raw price)
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
    "volume_price_corr",
    # Candle patterns
    "body_ratio",
    "upper_shadow",
    "lower_shadow",
    # Additional momentum / mean-reversion
    "rsi_slope",
    "ret_5_vs_vol",
    "close_vs_high20",
    "close_vs_low20",
    # Momentum divergence
    "price_rsi_divergence",
    "momentum_acceleration",
    # Regime features (binary market condition flags)
    "high_vol_regime",
    "low_vol_regime",
    "trend_up",
    "trend_strength",
    # New: Mean reversion signals
    "mean_reversion_signal",
    "price_momentum_ratio",
    # New: Trend quality
    "trend_consistency",
    "breakout_strength",
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
    
    # --- Lag features (capture autocorrelation patterns) ---
    data["ret_1_lag1"] = data["ret_1"].shift(1)
    data["ret_1_lag2"] = data["ret_1"].shift(2)
    data["ret_1_lag3"] = data["ret_1"].shift(3)

    # --- Volatility ---
    data["volatility"] = data["close"].pct_change().rolling(config.vol_window).std()
    
    # ATR normalized by close price (position-independent)
    tr = pd.concat([
        data["high"] - data["low"],
        (data["high"] - data["close"].shift(1)).abs(),
        (data["low"] - data["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    data["atr_norm"] = tr.rolling(14).mean() / data["close"]
    data["volatility_change"] = data["volatility"].pct_change(5)  # Volatility momentum

    # --- Trend Indicators ---
    data["rsi"] = compute_rsi(data["close"], period=config.rsi_period)
    data["rsi_normalized"] = (data["rsi"] - 50) / 50  # Normalize to [-1, 1]
    _, _, macd_hist = compute_macd(data["close"])
    data["macd_hist"] = macd_hist

    data["adx"] = compute_adx(data)
    data["macd_hist_change"] = data["macd_hist"].diff(3)  # MACD momentum

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
    # Volume zero-check BEFORE computing volume-based features
    zero_vol_mask = data["volume"].fillna(0) == 0
    if zero_vol_mask.any():
        data.loc[zero_vol_mask, "volume"] = np.nan

    data["volume_ma"] = data["volume"].rolling(config.vol_window).mean()
    data["volume_ratio"] = data["volume"] / data["volume_ma"]
    
    # OBV direction slope (sign of OBV change, not pct_change of cumsum)
    obv_direction = ((data["close"] > data["close"].shift(1)).astype(int) * 2 - 1)
    data["obv_slope"] = obv_direction.rolling(10).mean()  # -1 to +1 smoothed direction
    
    # Volume-price correlation (smart money indicator)
    data["volume_price_corr"] = data["ret_1"].rolling(20).corr(data["volume_ratio"])
    
    # --- Candle Body Patterns ---
    candle_range = data["high"] - data["low"]
    candle_range = candle_range.replace(0, np.nan)  # Avoid division by zero
    data["body_ratio"] = (data["close"] - data["open"]) / candle_range  # -1 to +1
    data["upper_shadow"] = (data["high"] - data[["open", "close"]].max(axis=1)) / candle_range
    data["lower_shadow"] = (data[["open", "close"]].min(axis=1) - data["low"]) / candle_range

    # --- Additional momentum / mean-reversion features ---
    data["rsi_slope"] = data["rsi"].diff(3) / 100.0  # RSI momentum, normalized to [-1, 1] range
    data["ret_5_vs_vol"] = data["ret_short"] / (data["volatility"] + 1e-8)  # Sharpe-like ratio
    rolling_high = data["high"].rolling(20).max().shift(1)
    rolling_low = data["low"].rolling(20).min().shift(1)
    data["close_vs_high20"] = (data["close"] - rolling_high) / rolling_high  # proximity to 20d high
    data["close_vs_low20"] = (data["close"] - rolling_low) / rolling_low    # proximity to 20d low
    
    # --- Momentum divergence (price vs RSI direction mismatch) ---
    price_direction = data["ret_short"].shift(1).rolling(5).mean()
    rsi_direction = data["rsi"].shift(1).diff(5) / 100
    data["price_rsi_divergence"] = price_direction - rsi_direction
    
    # Momentum acceleration (2nd derivative of price)
    data["momentum_acceleration"] = data["ret_1"].diff(3)

    # --- Regime features (from reference: high_vol, low_vol, trend_up, trend_strength) ---
    # These binary regime flags help the model separate market conditions
    vol_mean = data["volatility"].rolling(30).mean()
    vol_std = data["volatility"].rolling(30).std()
    vol_z = (data["volatility"] - vol_mean) / (vol_std + 1e-9)
    data["high_vol_regime"] = (vol_z > 0.5).astype(float)
    data["low_vol_regime"] = (vol_z < -0.5).astype(float)
    data["trend_up"] = (
        (data["price_vs_ema_slow"] > 0) &
        (data["ema_fast_slope"] > 0) &
        (data["macd_hist"] > 0)
    ).astype(float)
    data["trend_strength"] = (
        data["price_vs_ema_slow"].clip(-0.05, 0.05) +
        data["ema_fast_slope"].clip(-0.02, 0.02) +
        data["macd_hist"].clip(-0.5, 0.5) / 10
    )

    # --- New: Mean reversion signal (oversold/overbought with reversal) ---
    oversold = (data["rsi"] < 30) & (data["rsi"].diff() > 0)
    overbought = (data["rsi"] > 70) & (data["rsi"].diff() < 0)
    data["mean_reversion_signal"] = oversold.astype(float) - overbought.astype(float)
    
    # --- New: Price momentum ratio (short vs long momentum) ---
    data["price_momentum_ratio"] = data["ret_short"] / (data["ret_long"].abs() + 1e-8)
    data["price_momentum_ratio"] = data["price_momentum_ratio"].clip(-3, 3)
    
    # --- New: Trend consistency (how consistent is the trend direction) ---
    pos_days = (data["ret_1"] > 0).rolling(10).sum() / 10
    data["trend_consistency"] = (pos_days - 0.5) * 2  # Normalize to [-1, 1]
    
    # --- New: Breakout strength (price vs recent range) ---
    range_20 = rolling_high - rolling_low
    data["breakout_strength"] = (data["close"] - rolling_low) / (range_20 + 1e-8) - 0.5
    data["breakout_strength"] = data["breakout_strength"].clip(-1, 1)

    data = data.replace([np.inf, -np.inf], np.nan).dropna()
    return data
