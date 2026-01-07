import logging
import pandas as pd
import numpy as np
from typing import Dict
from sqlalchemy.orm import Session
from app.db.models_candles import Candle15m

logger = logging.getLogger(__name__)


def _ta_signal_15m_from_df(df: pd.DataFrame) -> Dict:
    if len(df) < 100:
        return {
            "signal": "NO_TRADE",
            "confidence": 0,
            "reason": "Not enough candles",
            "indicators": {},
            "quality_checks": {},
            "quality_score": 0,
            "trade_readiness_score": 0,
            "iv_regime": None,
            "bias": "NEUTRAL",
        }

    # ================================================================
    # BUILD DATAFRAME WITH ALL INDICATORS
    # ================================================================
    df = df.copy()

    # ================================================================
    # TREND INDICATORS
    # ================================================================
    df["sma_20"] = df["close"].rolling(20).mean()
    df["sma_50"] = df["close"].rolling(50).mean()
    df["ema_20"] = df["close"].ewm(span=20).mean()
    df["ema_50"] = df["close"].ewm(span=50).mean()
    df["ema_20_slope"] = df["ema_20"].diff()

    # ADX (Average Directional Index)
    df["adx"] = compute_adx(df)

    # ================================================================
    # MOMENTUM INDICATORS
    # ================================================================
    df["rsi"] = compute_rsi(df["close"])
    df["macd"], df["macd_signal"], df["macd_hist"] = compute_macd(df["close"])

    # Stochastic
    df["stoch_k"], df["stoch_d"] = compute_stochastic(df["high"], df["low"], df["close"])

    # ================================================================
    # VOLATILITY & VOLUME
    # ================================================================
    df["bb_upper"], df["bb_middle"], df["bb_lower"] = compute_bollinger_bands(df["close"])
    df["volatility_pct"] = df["close"].pct_change().rolling(20).std() * 100
    df["volume_ma"] = df["volume"].rolling(20).mean()
    df["volume_ratio"] = df["volume"] / df["volume_ma"]

    # Some instruments (e.g., index candles) can have volume=0.
    # Avoid penalizing the quality gate due to missing volume data.
    if float(df["volume"].fillna(0).sum()) == 0.0:
        df["volume_ratio"] = 1.0

    last = df.iloc[-1]

    # ================================================================
    # QUALITY CHECKS (minimum 4/8 required)
    # ================================================================
    quality_checks = {
        "adx_strong": float(last["adx"]) >= 25,
        "time_ok": True,  # 15-min is active time
        "stoch_ok": 30 <= float(last["stoch_k"]) <= 70,
        "vix_ok": True,  # Will be fetched separately if needed
        "bb_confirm": is_bb_confirming(last),
        "iv_trade_ok": False,  # Will be set from external IV data
        "vol_strong": True if float(df["volume"].fillna(0).sum()) == 0.0 else float(last["volume_ratio"]) > 1.5,
        "sr_confirm": True,  # Will be set from support/resistance
    }

    quality_score = sum([1 for v in quality_checks.values() if v])

    # ================================================================
    # MARKET BIAS & SIGNAL
    # ================================================================
    is_bullish = (
        last["ema_20"] > last["ema_50"]
        and last["ema_20_slope"] > 0
        and float(last["rsi"]) > 50
    )

    is_bearish = (
        last["ema_20"] < last["ema_50"]
        and last["ema_20_slope"] < 0
        and float(last["rsi"]) < 50
    )

    if is_bullish:
        signal = "BULLISH"
        bias = "BULLISH"
        confidence = 70 + min(10, quality_score * 2)  # Boost confidence with quality
        reason = "EMA trend up + RSI > 50 + ADX strong"
    elif is_bearish:
        signal = "BEARISH"
        bias = "BEARISH"
        confidence = 70 + min(10, quality_score * 2)
        reason = "EMA trend down + RSI < 50 + ADX strong"
    else:
        signal = "RANGE"
        bias = "NEUTRAL"
        confidence = 45
        reason = "No directional edge or ADX weak"

    # ================================================================
    # TRADE READINESS SCORE (0-100)
    # ================================================================
    trend_score = min(100, max(0, (float(last["adx"]) - 10) * 4))  # 10-25 → 0-60
    momentum_score = abs(float(last["rsi"]) - 50) * 2  # 0-100
    readiness_score = int((quality_score * 10) + (trend_score * 0.3) + (momentum_score * 0.1))
    readiness_score = min(100, readiness_score)

    # ================================================================
    # IV REGIME (defaults to NORMAL unless provided externally)
    # ================================================================
    iv_regime = "NORMAL"  # Will be overridden by external IV data if available

    # ================================================================
    # RETURN COMPLETE SIGNAL
    # ================================================================
    return {
        # Basic Signal
        "signal": signal,
        "confidence": min(100, float(confidence)),
        "reason": reason,

        # Market Context
        "bias": bias,
        "iv_regime": iv_regime,

        # Quality Assessment
        "quality_checks": quality_checks,
        "quality_score": quality_score,
        "trade_readiness_score": readiness_score,

        # All Indicators
        "indicators": {
            "adx": round(float(last["adx"]), 2),
            "rsi": round(float(last["rsi"]), 2),
            "macd_hist": round(float(last["macd_hist"]), 4),
            "stoch_k": round(float(last["stoch_k"]), 2),
            "stoch_d": round(float(last["stoch_d"]), 2),
            "sma_20": round(float(last["sma_20"]), 2),
            "sma_50": round(float(last["sma_50"]), 2),
            "ema_20": round(float(last["ema_20"]), 2),
            "ema_50": round(float(last["ema_50"]), 2),
            "bb_upper": round(float(last["bb_upper"]), 2),
            "bb_middle": round(float(last["bb_middle"]), 2),
            "bb_lower": round(float(last["bb_lower"]), 2),
            "volatility_pct": round(float(last["volatility_pct"]), 4),
            "volume_ratio": round(float(last["volume_ratio"]), 2),
            # India VIX & IV Rank are now fetched from APIs in signals.py
            # and added via enrich_signal_with_iv()
        },

        # Trend Analysis
        "trend_score": int(trend_score),
    }


def ta_signal_15m_from_candles(candles: list[dict]) -> Dict:
    """Same TA as ta_signal_15m(), but computed from in-memory candles.

    Expects candles in chronological order (oldest → newest) where each candle
    has keys: open, high, low, close, volume.
    """
    if len(candles) < 100:
        return {
            "signal": "NO_TRADE",
            "confidence": 0,
            "reason": "Not enough candles",
            "indicators": {},
            "quality_checks": {},
            "quality_score": 0,
            "trade_readiness_score": 0,
            "iv_regime": None,
            "bias": "NEUTRAL",
        }

    df = pd.DataFrame(
        [
            {
                "close": float(c.get("close")),
                "high": float(c.get("high")),
                "low": float(c.get("low")),
                "open": float(c.get("open")),
                "volume": float(c.get("volume", 0) or 0),
            }
            for c in candles
        ]
    )
    return _ta_signal_15m_from_df(df)

def ta_signal_15m(db: Session, symbol: str) -> Dict:
    """
    COMPREHENSIVE 15-minute technical analysis signal.
    Returns: Full market context + indicators + quality checks.
    """
    symbol = symbol.upper().strip()
    candles = (
        db.query(Candle15m)
        .filter(Candle15m.symbol == symbol)
        .order_by(Candle15m.timestamp.desc())
        .limit(300)
        .all()
    )

    logger.info(
        "TA DEBUG | symbol=%s | candles_found=%d",
        symbol,
        len(candles),
    )

    if len(candles) < 100:
        return {
            "signal": "NO_TRADE",
            "confidence": 0,
            "reason": "Not enough candles",
            "indicators": {},
            "quality_checks": {},
            "quality_score": 0,
            "trade_readiness_score": 0,
            "iv_regime": None,
            "bias": "NEUTRAL",
        }

    df = pd.DataFrame(
        [
            {
                "close": c.close,
                "high": c.high,
                "low": c.low,
                "open": c.open,
                "volume": c.volume,
            }
            for c in reversed(candles)
        ]
    )
    return _ta_signal_15m_from_df(df)


def compute_rsi(series: pd.Series, period: int = 14):
    """RSI (Relative Strength Index) - Professional TA-Lib standard"""
    delta = series.diff()
    
    # Separate gains and losses
    gains = delta.where(delta > 0, 0)
    losses = -delta.where(delta < 0, 0)
    
    # Wilder's smoothing for RSI (same as ATR)
    avg_gain = pd.Series(index=series.index, dtype=float)
    avg_loss = pd.Series(index=series.index, dtype=float)
    
    avg_gain.iloc[period] = gains.iloc[1:period+1].mean()
    avg_loss.iloc[period] = losses.iloc[1:period+1].mean()
    
    # Wilder's smoothing for rest
    for i in range(period + 1, len(series)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gains.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + losses.iloc[i]) / period
    
    # Calculate RS and RSI
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def compute_adx(df: pd.DataFrame, period: int = 14):
    """ADX (Average Directional Index) - TA-Lib standard with Wilder's smoothing"""
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    
    # True Range calculation
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1])
        )
    )
    
    # Up and Down moves
    up_move = high[1:] - high[:-1]
    down_move = low[:-1] - low[1:]
    
    # +DM and -DM
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    
    # Wilder's smoothing for ATR
    atr = np.zeros(len(tr))
    atr[period-1] = tr[:period].mean()
    for i in range(period, len(tr)):
        atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
    
    # Wilder's smoothing for DMs
    plus_dm_smooth = np.zeros(len(plus_dm))
    minus_dm_smooth = np.zeros(len(minus_dm))
    plus_dm_smooth[period-1] = plus_dm[:period].sum()
    minus_dm_smooth[period-1] = minus_dm[:period].sum()
    
    for i in range(period, len(plus_dm)):
        plus_dm_smooth[i] = plus_dm_smooth[i-1] - plus_dm_smooth[i-1]/period + plus_dm[i]
        minus_dm_smooth[i] = minus_dm_smooth[i-1] - minus_dm_smooth[i-1]/period + minus_dm[i]
    
    # +DI and -DI
    plus_di = np.divide(plus_dm_smooth, atr, where=atr!=0, out=np.zeros_like(atr)) * 100
    minus_di = np.divide(minus_dm_smooth, atr, where=atr!=0, out=np.zeros_like(atr)) * 100
    
    # DX
    di_sum = plus_di + minus_di
    dx = np.divide(
        np.abs(plus_di - minus_di),
        di_sum,
        where=di_sum!=0,
        out=np.zeros_like(di_sum)
    ) * 100
    
    # ADX with Wilder's smoothing
    adx = np.zeros(len(dx))
    adx[2*period-2] = dx[period-1:2*period-1].mean()
    for i in range(2*period-1, len(dx)):
        adx[i] = (adx[i-1] * (period - 1) + dx[i]) / period
    
    # Prepend NaN for the removed first value and convert to Series
    adx_series = pd.Series([np.nan] + list(adx), index=df.index)
    return adx_series.bfill()


def compute_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD (Moving Average Convergence Divergence)"""
    ema_fast = series.ewm(span=fast).mean()
    ema_slow = series.ewm(span=slow).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal).mean()
    macd_hist = macd - macd_signal
    return macd, macd_signal, macd_hist


def compute_stochastic(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14):
    """Stochastic Oscillator"""
    highest_high = high.rolling(period).max()
    lowest_low = low.rolling(period).min()
    
    k = ((close - lowest_low) / (highest_high - lowest_low)) * 100
    d = k.rolling(3).mean()
    
    return k, d


def compute_bollinger_bands(series: pd.Series, period: int = 20, std_dev: int = 2):
    """Bollinger Bands"""
    sma = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower


def is_bb_confirming(row) -> bool:
    """Check if price is confirming Bollinger Bands logic"""
    try:
        close = float(row["close"])
        bb_upper = float(row["bb_upper"])
        bb_lower = float(row["bb_lower"])
        # Confirming if not at extremes
        return bb_lower < close < bb_upper
    except:
        return False
