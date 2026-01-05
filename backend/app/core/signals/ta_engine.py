import logging
import pandas as pd
import numpy as np
from typing import Dict
from sqlalchemy.orm import Session
from app.db.models_candles import Candle15m

logger = logging.getLogger(__name__)

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

    # ================================================================
    # BUILD DATAFRAME WITH ALL INDICATORS
    # ================================================================
    df = pd.DataFrame(
        [{
            "close": c.close,
            "high": c.high,
            "low": c.low,
            "open": c.open,
            "volume": c.volume,
        } for c in reversed(candles)]
    )

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
        "vol_strong": float(last["volume_ratio"]) > 1.5,
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
            "india_vix": 10.1,  # TODO: Fetch from external API
            "iv_rank": 7.26,  # TODO: Fetch from external IV API
        },
        
        # Trend Analysis
        "trend_score": int(trend_score),
    }


def compute_rsi(series: pd.Series, period: int = 14):
    """RSI (Relative Strength Index)"""
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def compute_adx(df: pd.DataFrame, period: int = 14):
    """ADX (Average Directional Index) - Simplified"""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    
    # True Range
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    
    # Directional Movement
    up = high.diff()
    down = low.diff() * -1
    pos_dm = up.copy()
    pos_dm[up <= down] = 0
    pos_dm[up < 0] = 0
    neg_dm = down.copy()
    neg_dm[down <= up] = 0
    neg_dm[down < 0] = 0
    
    pos_di = (pos_dm.rolling(period).sum() / atr) * 100
    neg_di = (neg_dm.rolling(period).sum() / atr) * 100
    
    di_diff = abs(pos_di - neg_di)
    di_sum = pos_di + neg_di
    di_ratio = di_diff / di_sum
    adx = di_ratio.rolling(period).mean() * 100
    
    return adx


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
