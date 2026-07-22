"""
context.py
-----------
Builds market context from comprehensive signal output.
Now extracts full market data from enhanced ta_signal_15m.
"""

from typing import Dict, Any


def build_market_context(sig: Dict[str, Any]) -> Dict[str, Any]:
    """
    Builds complete market context from signal.

    Input:
        sig -> output of ta_signal_15m() or generate_signal()
        {
            signal, confidence, bias, iv_regime,
            quality_checks, quality_score, trade_readiness_score,
            indicators: {adx, rsi, macd, stoch, bb, volatility, etc}
        }

    Output:
        {
            market_mode,
            vol_state,
            iv_regime,
            bias,
            quality_checks,
            quality_score,
            trade_readiness_score,
            indicators
        }
    """

    indicators = sig.get("indicators", {}) or {}

    # ============================
    # MARKET MODE (TREND / RANGE / BREAKOUT_SETUP)
    # ============================
    market_mode = "RANGE"
    try:
        adx = float(indicators.get("adx", 0))
        macd_hist = float(indicators.get("macd_hist", 0))
        bias_val = sig.get("bias", "NEUTRAL")
        if adx >= 25:
            market_mode = "TRENDING"
        elif adx >= 18 and bias_val != "NEUTRAL" and abs(macd_hist) > 0:
            # ADX building momentum + directional bias → treat as breakout setup
            market_mode = "BREAKOUT_SETUP"
    except (ValueError, TypeError):
        pass

    # ============================
    # VOLATILITY STATE (INDIA VIX)
    # ============================
    vol_state = "NORMAL"
    try:
        india_vix = indicators.get("india_vix", 15)
        if india_vix is not None:
            india_vix = float(india_vix)
            if india_vix >= 20:
                vol_state = "HIGH"
            elif india_vix <= 13:
                vol_state = "LOW"
    except (ValueError, TypeError):
        vol_state = "NORMAL"

    # ============================
    # IV REGIME (from signal or defaults)
    # ============================
    iv_regime = sig.get("iv_regime", "NORMAL")

    # ============================
    # DIRECTIONAL BIAS
    # ============================
    bias = sig.get("bias", "NEUTRAL")

    # ============================
    # QUALITY CHECKS & SCORE
    # ============================
    quality_checks = sig.get("quality_checks", {})
    quality_score = sig.get("quality_score", 0)
    trade_readiness_score = sig.get("trade_readiness_score", 0)

    # ============================
    # DAY CHANGE CONTEXT
    # How much has the market moved today vs previous close.
    # A flat open after a strong prior-day move signals that the
    # market has absorbed (not continued) that directional momentum.
    # ============================
    day_change_pct = 0.0
    open_type = "UNKNOWN"
    try:
        day_change_pct = float(indicators.get("day_change_pct", 0.0))
        open_type = indicators.get("open_type", "UNKNOWN") or "UNKNOWN"
    except (ValueError, TypeError):
        pass

    return {
        # Core context
        "market_mode": market_mode,
        "vol_state": vol_state,
        "iv_regime": iv_regime,
        "bias": bias,
        
        # Quality metrics
        "quality_checks": quality_checks,
        "quality_score": quality_score,
        "trade_readiness_score": trade_readiness_score,
        
        # All indicators for strategy decisions
        "indicators": indicators,
        
        # Trend strength
        "trend_score": sig.get("trend_score", 0),

        # Day change context (intraday move vs previous day close)
        "day_change_pct": day_change_pct,
        "open_type": open_type,
    }
