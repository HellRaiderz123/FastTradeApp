"""
decision.py
------------
Pure strategy-decision logic.
Decides WHAT strategy to take, not HOW.
"""

from typing import Dict, Any, Tuple


def decide_strategy(
    sig: Dict[str, Any],
    ctx: Dict[str, Any],
    confidence: float,
    min_confidence: float,
) -> Tuple[str, str]:
    """
    Decide which strategy to use.

    Returns:
        (strategy_mode, reason)

    strategy_mode:
        - BULL_PUT
        - BEAR_CALL
        - IRON_CONDOR
        - NO_TRADE
    """

    rec = sig.get("recommendation")
    bias = ctx.get("bias", "NEUTRAL")

    # Direction helpers (exactly like Streamlit)
    take_bull = rec == "BUY_CE" or (bias == "BULLISH" and rec != "BUY_PE")
    take_bear = rec == "BUY_PE" or (bias == "BEARISH" and rec != "BUY_CE")

    market_mode = ctx.get("market_mode")
    iv_regime = ctx.get("iv_regime")

    # =================================================
    # TRENDING MARKET → DIRECTIONAL CREDIT SPREADS
    # =================================================
    if market_mode == "TRENDING" and iv_regime in ["LOW", "NORMAL"]:

        # PATCH 6 logic preserved
        spread_min_conf = 65 if iv_regime == "LOW" else min_confidence

        if confidence >= spread_min_conf:
            if take_bull:
                return "BULL_PUT", "Trending market with bullish bias"
            if take_bear:
                return "BEAR_CALL", "Trending market with bearish bias"
            return "NO_TRADE", "Trend present but directional bias unclear"

        return "NO_TRADE", "Trend present but confidence too low"

    # =================================================
    # RANGE MARKET + HIGH IV → IRON CONDOR
    # =================================================
    if market_mode == "RANGE" and iv_regime == "HIGH":
        return "IRON_CONDOR", "Range-bound market with high IV"

    # =================================================
    # EVERYTHING ELSE → NO TRADE
    # =================================================
    return "NO_TRADE", "Unfavorable volatility or structure"
