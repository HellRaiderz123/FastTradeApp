"""
decision.py
------------
Pure strategy-decision logic.
Decides WHAT strategy to take, not HOW.
Now with quality-based filtering.
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

    bias = ctx.get("bias", "NEUTRAL")
    market_mode = ctx.get("market_mode")
    iv_regime = ctx.get("iv_regime")
    quality_score = ctx.get("quality_score", 0)
    quality_checks = ctx.get("quality_checks", {})

    # ================================================
    # QUALITY GATE (minimum 4/8 required)
    # ================================================
    if quality_score < 4:
        return "NO_TRADE", f"Insufficient quality score ({quality_score}/8)"

    # Direction helpers
    take_bull = bias == "BULLISH"
    take_bear = bias == "BEARISH"

    # Confidence thresholds tuned by IV regime (allow low-IV trades but keep guardrails)
    spread_min_conf = min_confidence
    if iv_regime == "LOW":
        spread_min_conf = max(55, min_confidence - 10)
    elif iv_regime == "NORMAL":
        spread_min_conf = max(60, min_confidence - 5)

    # =================================================
    # TRENDING MARKET → DIRECTIONAL CREDIT SPREADS
    # =================================================
    if market_mode == "TRENDING":

        if confidence >= spread_min_conf:
            if take_bull:
                return "BULL_PUT", f"Trending bullish (conf={confidence:.0f}%, iv={iv_regime}, quality={quality_score}/8)"
            if take_bear:
                return "BEAR_CALL", f"Trending bearish (conf={confidence:.0f}%, iv={iv_regime}, quality={quality_score}/8)"
            return "NO_TRADE", "Trend present but directional bias unclear"

        return "NO_TRADE", f"Trend present but confidence too low ({confidence:.0f}% < {spread_min_conf}%)"

    # =================================================
    # RANGE MARKET + HIGH IV → IRON CONDOR
    # =================================================
    if market_mode == "RANGE" and iv_regime == "HIGH":
        if quality_score >= 5:  # Stricter for IC
            return "IRON_CONDOR", "Range-bound market with high IV (IC appropriate)"
        return "NO_TRADE", "Range market + high IV but insufficient quality"

    # =================================================
    # NEUTRAL/LOW IV + RANGE: allow directional only when bias+confidence are clear
    # =================================================
    if market_mode == "RANGE" and iv_regime in ["LOW", "NORMAL"]:
        if confidence >= spread_min_conf:
            if take_bull:
                return "BULL_PUT", f"Range but bullish bias; low/normal IV (conf={confidence:.0f}%, quality={quality_score}/8)"
            if take_bear:
                return "BEAR_CALL", f"Range but bearish bias; low/normal IV (conf={confidence:.0f}%, quality={quality_score}/8)"
        return "NO_TRADE", "Range + low/normal IV without strong bias/confidence"

    # =================================================
    # FALLBACK
    # =================================================
    return "NO_TRADE", f"Unfavorable structure (mode={market_mode}, iv={iv_regime})"
