"""
context.py
-----------
Builds market context from signal output.
Pure logic. No UI. No API calls.
"""

from typing import Dict, Any


def build_market_context(sig: Dict[str, Any]) -> Dict[str, Any]:
    """
    Builds market context exactly as in Streamlit.

    Input:
        sig -> output of recommend_smart_option()

    Output:
        {
            market_mode,
            vol_state,
            iv_regime,
            bias,
            indicators
        }
    """

    tech = sig.get("technical_analysis", {})
    indicators = tech.get("indicators", {}) or {}

    # ============================
    # MARKET MODE (TREND / RANGE)
    # ============================
    market_mode = "RANGE"
    try:
        if float(indicators.get("adx", 0)) >= 25:
            market_mode = "TRENDING"
    except Exception:
        pass

    # ============================
    # VOLATILITY STATE (INDIA VIX)
    # ============================
    vol_state = "NORMAL"
    try:
        india_vix = indicators.get("india_vix")
        if india_vix is not None:
            india_vix = float(india_vix)
            if india_vix >= 20:
                vol_state = "HIGH"
            elif india_vix <= 13:
                vol_state = "LOW"
    except Exception:
        pass

    # ============================
    # IV REGIME
    # ============================
    iv_regime = indicators.get("iv_regime")
    if iv_regime is None:
        iv_regime = tech.get("iv_regime")

    # ============================
    # DIRECTIONAL BIAS
    # ============================
    bias = tech.get("bias", "NEUTRAL")

    return {
        "market_mode": market_mode,
        "vol_state": vol_state,
        "iv_regime": iv_regime,
        "bias": bias,
        "indicators": indicators,
    }
