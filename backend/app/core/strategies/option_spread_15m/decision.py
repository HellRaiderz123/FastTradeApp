"""
decision.py
------------
Pure strategy-decision logic.
Decides WHAT strategy to take, not HOW.
Now with regime-based strategy unlocking.
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
        - CALL_RATIO_BACKSPREAD
        - PUT_RATIO_BACKSPREAD
        - NO_TRADE
    """

    bias = ctx.get("bias", "NEUTRAL")
    market_mode = ctx.get("market_mode")
    iv_regime = ctx.get("iv_regime")
    quality_score = ctx.get("quality_score", 0)
    indicators = ctx.get("indicators", {})

    adx = indicators.get("adx", 0)

    # ================================================
    # HARD QUALITY GATE
    # ================================================
    if quality_score < 4:
        return "NO_TRADE", f"Insufficient quality score ({quality_score}/8)"

    take_bull = bias == "BULLISH"
    take_bear = bias == "BEARISH"

    # Confidence thresholds (adaptive by IV)
    spread_min_conf = min_confidence
    if iv_regime == "LOW":
        spread_min_conf = max(55, min_confidence - 10)
    elif iv_regime == "NORMAL":
        spread_min_conf = max(60, min_confidence - 5)

    # Ratio strategies require stronger conviction
    ratio_min_conf = max(65, min_confidence)
    ratio_quality_min = 6

    # ================================================
    # BREAKOUT / STRONG TREND → RATIO BACKSPREADS
    # ================================================
    if market_mode in ["TRENDING", "BREAKOUT_SETUP"]:
        if (
            adx >= 20
            and iv_regime in ["LOW", "NORMAL"]
            and confidence >= ratio_min_conf
            and quality_score >= ratio_quality_min
        ):
            if take_bull:
                return (
                    "CALL_RATIO_BACKSPREAD",
                    f"Strong bullish move expected (ADX={adx:.1f}, IV={iv_regime}, conf={confidence:.0f}%)",
                )
            if take_bear:
                return (
                    "PUT_RATIO_BACKSPREAD",
                    f"Strong bearish move expected (ADX={adx:.1f}, IV={iv_regime}, conf={confidence:.0f}%)",
                )

        # Fallback inside trend → safer spreads
        if confidence >= spread_min_conf:
            if take_bull:
                return "BULL_PUT", f"Trending bullish but breakout not strong enough (ADX={adx:.1f})"
            if take_bear:
                return "BEAR_CALL", f"Trending bearish but breakout not strong enough (ADX={adx:.1f})"

        return "NO_TRADE", "Trend present but conviction insufficient"

    # ================================================
    # RANGE + HIGH IV → IRON CONDOR
    # ================================================
    if market_mode == "RANGE" and iv_regime == "HIGH":
        if quality_score >= 5:
            return "IRON_CONDOR", "Range-bound market with high IV"
        return "NO_TRADE", "Range + high IV but insufficient quality"

    # ================================================
    # RANGE + LOW/NORMAL IV → DIRECTIONAL SPREADS ONLY
    # ================================================
    if market_mode == "RANGE" and iv_regime in ["LOW", "NORMAL"]:
        if confidence >= spread_min_conf:
            if take_bull:
                return "BULL_PUT", f"Range but bullish bias (conf={confidence:.0f}%)"
            if take_bear:
                return "BEAR_CALL", f"Range but bearish bias (conf={confidence:.0f}%)"
        return "NO_TRADE", "Range + low/normal IV without strong bias"

    # ================================================
    # FALLBACK
    # ================================================
    return "NO_TRADE", f"Unfavorable structure (mode={market_mode}, iv={iv_regime})"
