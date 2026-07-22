import logging
import pandas as pd
import numpy as np
from typing import Dict
from sqlalchemy.orm import Session
from app.db.models_candles import Candle15m, CandleDaily

logger = logging.getLogger(__name__)


def _drop_price_anomalies(df: pd.DataFrame, gap_threshold: float = 0.05):
    """Remove obvious bad candles where close-to-close gap exceeds threshold.

    Large gaps (e.g., bad feed spikes) inflate ATR and suppress ADX.
    Returns the cleaned dataframe, number of rows dropped, and first bad index.
    """
    gap = df["close"].pct_change().abs()
    bad_mask = gap > gap_threshold
    dropped = int(bad_mask.sum())
    if dropped == 0:
        return df, 0, None

    first_bad_idx = int(bad_mask.idxmax()) if bad_mask.any() else None
    logger.warning(
        "TA CLEANUP | dropping %d candles due to close gap > %.1f%% | first_bad_idx=%s",
        dropped,
        gap_threshold * 100,
        first_bad_idx,
    )
    cleaned = df.loc[~bad_mask].reset_index(drop=True)
    return cleaned, dropped, first_bad_idx


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

    # Remove obvious price anomalies (e.g., feed spikes >5% gap)
    df, dropped, first_bad = _drop_price_anomalies(df, gap_threshold=0.05)
    if len(df) < 100:
        return {
            "signal": "NO_TRADE",
            "confidence": 0,
            "reason": f"Not enough candles after cleanup (dropped {dropped})",
            "indicators": {},
            "quality_checks": {},
            "quality_score": 0,
            "trade_readiness_score": 0,
            "iv_regime": None,
            "bias": "NEUTRAL",
        }

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
        "vol_strong": True if float(df["volume"].fillna(0).sum()) == 0.0 else float(last["volume_ratio"]) > 1.2,
        "sr_confirm": True,  # Will be set from support/resistance
    }

    quality_score = sum([1 for v in quality_checks.values() if v])

    # ================================================================
    # MARKET BIAS & SIGNAL (with divergence detection)
    # ================================================================
    # Separate EMA trend from slope for more nuanced signal detection
    ema_trend_bullish = last["ema_20"] > last["ema_50"]
    ema_trend_bearish = last["ema_20"] < last["ema_50"]
    ema_slope_positive = last["ema_20_slope"] > 0
    ema_slope_negative = last["ema_20_slope"] < 0
    rsi_bullish = float(last["rsi"]) > 50
    rsi_bearish = float(last["rsi"]) < 50
    adx_strong = float(last["adx"]) >= 25

    # STRONG SIGNALS: EMA trend + slope + RSI all aligned + ADX confirmation
    if ema_trend_bullish and ema_slope_positive and rsi_bullish and adx_strong:
        signal = "BULLISH"
        bias = "BULLISH"
        confidence = 70 + min(10, quality_score * 2)
        reason = "EMA trend up + RSI > 50 + ADX strong"
    elif ema_trend_bearish and ema_slope_negative and rsi_bearish and adx_strong:
        signal = "BEARISH"
        bias = "BEARISH"
        confidence = 70 + min(10, quality_score * 2)
        reason = "EMA trend down + RSI < 50 + ADX strong"
    
    # MEDIUM SIGNALS: EMA trend + ADX strong, but RSI/slope divergence
    elif adx_strong and ema_trend_bearish:
        signal = "BEARISH"
        bias = "BEARISH"
        confidence = 55 + min(7, quality_score)
        if rsi_bullish:
            reason = "EMA bearish + strong ADX but RSI divergence (caution: potential reversal)"
        else:
            reason = "EMA bearish + strong ADX but slope divergence (weakening trend)"
    elif adx_strong and ema_trend_bullish:
        signal = "BULLISH"
        bias = "BULLISH"
        confidence = 55 + min(7, quality_score)
        if rsi_bearish:
            reason = "EMA bullish + strong ADX but RSI divergence (caution: potential reversal)"
        else:
            reason = "EMA bullish + strong ADX but slope divergence (weakening trend)"
    
    # TRUE RANGE: Weak ADX or no clear trend
    else:
        signal = "RANGE"
        bias = "NEUTRAL"
        # Use quality score to differentiate a clean range from a noisy one
        confidence = 35 + min(15, quality_score * 2)
        reason = "No directional edge or ADX weak"

    # ================================================================
    # TRADE READINESS SCORE (0-100)
    # ================================================================
    trend_score = min(100, max(0, (float(last["adx"]) - 10) * 4))  # 10-25 → 0-60
    momentum_score = abs(float(last["rsi"]) - 50) * 2  # 0-100
    # Avoid NaN/inf propagating into readiness score
    readiness_score = (quality_score * 10) + (trend_score * 0.3) + (momentum_score * 0.1)
    readiness_score = int(np.nan_to_num(readiness_score, nan=0.0, posinf=0.0, neginf=0.0))
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

    result = _ta_signal_15m_from_df(df)

    # Attach diagnostics so UI/logs can validate freshness
    try:
        last_ts = candles[0].timestamp if candles else None
        result["diagnostics"] = {
            "candle_count": len(candles),
            "last_candle_ts": last_ts.isoformat() if last_ts else None,
            "last_close": candles[0].close if candles else None,
        }
    except Exception:
        pass

    # ================================================================
    # DAY CHANGE CONTEXT
    # Computes today's intraday change vs previous day's close.
    # Prevents lagging TA indicators (EMA/ADX from prior day's strong
    # move) from triggering aggressive directional strategies on a flat
    # or reversal open.
    # ================================================================
    try:
        today_date = candles[0].timestamp.date()
        today_candles = [c for c in candles if c.timestamp.date() == today_date]
        prev_candles = [c for c in candles if c.timestamp.date() < today_date]

        if today_candles and prev_candles:
            # latest close today vs last close of previous trading day
            today_latest_close = today_candles[0].close   # candles sorted desc → [0] is most recent
            prev_day_close = prev_candles[0].close        # most recent candle of previous day

            if prev_day_close and prev_day_close != 0:
                day_change_pct = (today_latest_close - prev_day_close) / prev_day_close * 100
                day_change_pct = round(day_change_pct, 3)

                if abs(day_change_pct) <= 0.5:
                    open_type = "FLAT"
                elif day_change_pct > 1.5:
                    open_type = "STRONG_GAP_UP"
                elif day_change_pct > 0.5:
                    open_type = "GAP_UP"
                elif day_change_pct < -1.5:
                    open_type = "STRONG_GAP_DOWN"
                else:
                    open_type = "GAP_DOWN"

                if result.get("indicators") is None:
                    result["indicators"] = {}
                result["indicators"]["day_change_pct"] = day_change_pct
                result["indicators"]["open_type"] = open_type
                logger.info(
                    "DAY CHANGE | symbol=%s | day_change=%.3f%% | open_type=%s",
                    symbol,
                    day_change_pct,
                    open_type,
                )
    except Exception as e:
        logger.debug("Could not compute day change context: %s", e)

    return result


def _ta_signal_daily_from_df(df: pd.DataFrame) -> Dict:
    """Daily timeframe technical analysis for swing trading"""
    if len(df) < 200:
        return {
            "signal": "NO_TRADE",
            "confidence": 0,
            "reason": "Not enough daily candles",
            "indicators": {},
            "quality_checks": {},
            "quality_score": 0,
            "trade_readiness_score": 0,
            "iv_regime": None,
            "bias": "NEUTRAL",
        }

    df = df.copy()
    
    # Remove obvious price anomalies
    original_len = len(df)
    df, dropped, first_bad = _drop_price_anomalies(df, gap_threshold=0.10)  # Higher threshold for daily gaps
    if len(df) < 200:
        return {
            "signal": "NO_TRADE",
            "confidence": 0,
            "reason": f"Not enough candles after cleanup (dropped {dropped} from {original_len})",
            "indicators": {},
            "quality_checks": {},
            "quality_score": 0,
            "trade_readiness_score": 0,
            "iv_regime": None,
            "bias": "NEUTRAL",
        }

    # ================================================================
    # SWING TRADING INDICATORS (Daily timeframe)
    # ================================================================
    # Use longer EMAs for swing trading (50/200 instead of 20/50)
    df["sma_50"] = df["close"].rolling(50).mean()
    df["sma_200"] = df["close"].rolling(200).mean()
    df["ema_50"] = df["close"].ewm(span=50).mean()
    df["ema_200"] = df["close"].ewm(span=200).mean()
    df["ema_50_slope"] = df["ema_50"].diff()

    # ADX for trend strength
    df["adx"] = compute_adx(df)

    # Momentum indicators
    df["rsi"] = compute_rsi(df["close"])
    df["macd"], df["macd_signal"], df["macd_hist"] = compute_macd(df["close"])
    df["stoch_k"], df["stoch_d"] = compute_stochastic(df["high"], df["low"], df["close"])

    # Volatility & Volume
    df["bb_upper"], df["bb_middle"], df["bb_lower"] = compute_bollinger_bands(df["close"])
    df["volatility_pct"] = df["close"].pct_change().rolling(50).std() * 100  # 50-day volatility
    df["volume_ma"] = df["volume"].rolling(50).mean()
    df["volume_ratio"] = df["volume"] / df["volume_ma"]

    if float(df["volume"].fillna(0).sum()) == 0.0:
        df["volume_ratio"] = 1.0

    last = df.iloc[-1]

    # ================================================================
    # QUALITY CHECKS FOR SWING TRADING
    # ================================================================
    quality_checks = {
        "adx_strong": float(last["adx"]) >= 20,  # Lower threshold for daily
        "time_ok": True,
        "stoch_ok": 20 <= float(last["stoch_k"]) <= 80,  # Wider range for swing
        "vix_ok": True,
        "bb_confirm": is_bb_confirming(last),
        "iv_trade_ok": False,
        "vol_strong": True if float(df["volume"].fillna(0).sum()) == 0.0 else float(last["volume_ratio"]) > 1.2,  # Lower threshold
        "sr_confirm": True,
    }

    quality_score = sum([1 for v in quality_checks.values() if v])

    # ================================================================
    # SWING TRADING BIAS & SIGNAL (EMA 50/200 with divergence detection)
    # ================================================================
    # Separate trend from slope for daily timeframe
    ema_trend_bullish = last["ema_50"] > last["ema_200"]
    ema_trend_bearish = last["ema_50"] < last["ema_200"]
    ema_slope_positive = last["ema_50_slope"] > 0
    ema_slope_negative = last["ema_50_slope"] < 0
    rsi_bullish = float(last["rsi"]) >= 55  # Require clear bullish momentum for swing
    rsi_bearish = float(last["rsi"]) <= 45  # Require clear bearish momentum for swing
    adx_strong = float(last["adx"]) >= 20  # Daily timeframe threshold

    # STRONG SIGNALS: EMA trend + slope + RSI all aligned + ADX confirmation
    if ema_trend_bullish and ema_slope_positive and rsi_bullish and adx_strong:
        signal = "BULLISH"
        bias = "BULLISH"
        confidence = 65 + min(15, quality_score * 2)
        reason = "Daily EMA 50/200 cross up + RSI favorable + ADX strong"
    elif ema_trend_bearish and ema_slope_negative and rsi_bearish and adx_strong:
        signal = "BEARISH"
        bias = "BEARISH"
        confidence = 65 + min(15, quality_score * 2)
        reason = "Daily EMA 50/200 cross down + RSI favorable + ADX strong"
    
    # MEDIUM SIGNALS: EMA trend + ADX strong, but RSI/slope divergence
    elif adx_strong and ema_trend_bearish:
        signal = "BEARISH"
        bias = "BEARISH"
        confidence = 50 + min(10, quality_score)
        if rsi_bullish:
            reason = "Daily EMA bearish + strong ADX but RSI divergence (potential reversal watch)"
        else:
            reason = "Daily EMA bearish + strong ADX but slope divergence (weakening trend)"
    elif adx_strong and ema_trend_bullish:
        signal = "BULLISH"
        bias = "BULLISH"
        confidence = 50 + min(10, quality_score)
        if rsi_bearish:
            reason = "Daily EMA bullish + strong ADX but RSI divergence (potential reversal watch)"
        else:
            reason = "Daily EMA bullish + strong ADX but slope divergence (weakening trend)"
    
    # TRUE RANGE: Weak ADX or no clear trend
    else:
        signal = "RANGE"
        bias = "NEUTRAL"
        confidence = 40
        reason = "No clear daily trend or weak ADX"

    # ================================================================
    # TRADE READINESS SCORE
    # ================================================================
    trend_score = min(100, max(0, (float(last["adx"]) - 10) * 5))
    momentum_score = abs(float(last["rsi"]) - 50) * 1.5
    readiness_score = (quality_score * 10) + (trend_score * 0.4) + (momentum_score * 0.1)
    readiness_score = int(np.nan_to_num(readiness_score, nan=0.0, posinf=0.0, neginf=0.0))
    readiness_score = min(100, readiness_score)

    iv_regime = "NORMAL"

    return {
        "signal": signal,
        "confidence": min(100, float(confidence)),
        "reason": reason,
        "bias": bias,
        "iv_regime": iv_regime,
        "quality_checks": quality_checks,
        "quality_score": quality_score,
        "trade_readiness_score": readiness_score,
        "indicators": {
            "adx": round(float(last["adx"]), 2),
            "rsi": round(float(last["rsi"]), 2),
            "macd_hist": round(float(last["macd_hist"]), 4),
            "stoch_k": round(float(last["stoch_k"]), 2),
            "stoch_d": round(float(last["stoch_d"]), 2),
            "sma_50": round(float(last["sma_50"]), 2),
            "sma_200": round(float(last["sma_200"]), 2),
            "ema_50": round(float(last["ema_50"]), 2),
            "ema_200": round(float(last["ema_200"]), 2),
            "bb_upper": round(float(last["bb_upper"]), 2),
            "bb_middle": round(float(last["bb_middle"]), 2),
            "bb_lower": round(float(last["bb_lower"]), 2),
            "volatility_pct": round(float(last["volatility_pct"]), 4),
            "volume_ratio": round(float(last["volume_ratio"]), 2),
        },
    }


def ta_signal_daily_from_df(df: pd.DataFrame) -> Dict:
    """Public wrapper for daily TA analysis from a dataframe."""
    return _ta_signal_daily_from_df(df)


def ta_signal_daily(db: Session, symbol: str) -> Dict:
    """
    DAILY timeframe technical analysis for swing trading.
    Uses EMA 50/200 crossover strategy with wider stops.
    """
    symbol = symbol.upper().strip()
    candles = (
        db.query(CandleDaily)
        .filter(CandleDaily.symbol == symbol)
        .order_by(CandleDaily.date.desc())
        .limit(250)
        .all()
    )

    logger.info(
        "TA DAILY DEBUG | symbol=%s | candles_found=%d",
        symbol,
        len(candles),
    )

    if len(candles) < 200:
        return {
            "signal": "NO_TRADE",
            "confidence": 0,
            "reason": "Not enough daily candles",
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

    result = _ta_signal_daily_from_df(df)

    # Attach diagnostics
    try:
        last_date = candles[0].date if candles else None
        result["diagnostics"] = {
            "candle_count": len(candles),
            "last_candle_date": last_date.isoformat() if last_date else None,
            "last_close": candles[0].close if candles else None,
        }
    except Exception:
        pass

    return result


def compute_rsi(series: pd.Series, period: int = 14):
    """RSI (Relative Strength Index) using Wilder-style smoothing.

    Handles one-sided trend runs safely:
    - no losses -> RSI = 100
    - no gains -> RSI = 0
    - flat tape -> RSI = 50
    """
    delta = series.diff()

    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    avg_gain = gains.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    rsi = rsi.where(avg_loss != 0, 100.0)
    rsi = rsi.where(avg_gain != 0, 0.0)
    flat_mask = (avg_gain == 0) & (avg_loss == 0)
    rsi = rsi.mask(flat_mask, 50.0)

    return rsi.bfill()


def compute_adx(df: pd.DataFrame, period: int = 14):
    """ADX (Average Directional Index).

    Priority: use `ta` library (matches TradingView-style RMA smoothing).
    Fallback: custom Wilder smoothing implementation.
    """
    try:
        from ta.trend import ADXIndicator  # type: ignore

        indicator = ADXIndicator(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=period,
            fillna=False,
        )
        adx_series = indicator.adx()
        return adx_series.bfill()
    except Exception:
        pass

    # Fallback: Wilder smoothing
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1])
        )
    )
    up_move = high[1:] - high[:-1]
    down_move = low[:-1] - low[1:]
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    
    atr = np.zeros(len(tr))
    atr[period-1] = tr[:period].mean()
    for i in range(period, len(tr)):
        atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
    
    plus_dm_smooth = np.zeros(len(plus_dm))
    minus_dm_smooth = np.zeros(len(minus_dm))
    plus_dm_smooth[period-1] = plus_dm[:period].sum()
    minus_dm_smooth[period-1] = minus_dm[:period].sum()
    
    for i in range(period, len(plus_dm)):
        plus_dm_smooth[i] = plus_dm_smooth[i-1] - plus_dm_smooth[i-1]/period + plus_dm[i]
        minus_dm_smooth[i] = minus_dm_smooth[i-1] - minus_dm_smooth[i-1]/period + minus_dm[i]
    
    plus_di = np.divide(plus_dm_smooth, atr, where=atr!=0, out=np.zeros_like(atr)) * 100
    minus_di = np.divide(minus_dm_smooth, atr, where=atr!=0, out=np.zeros_like(atr)) * 100
    di_sum = plus_di + minus_di
    dx = np.divide(
        np.abs(plus_di - minus_di),
        di_sum,
        where=di_sum!=0,
        out=np.zeros_like(di_sum)
    ) * 100
    
    adx = np.zeros(len(dx))
    adx[2*period-2] = dx[period-1:2*period-1].mean()
    for i in range(2*period-1, len(dx)):
        adx[i] = (adx[i-1] * (period - 1) + dx[i]) / period
    
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
