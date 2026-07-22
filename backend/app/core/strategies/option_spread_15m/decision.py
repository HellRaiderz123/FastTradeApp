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
    # DAY CHANGE CONTEXT
    # How the market is trading today relative to yesterday's close.
    # A flat or near-flat open after a strong prior-day directional
    # move means the market has ABSORBED (not continued) that impulse.
    # Aggressive continuation strategies like Ratio Backspreads need
    # the market to actually be moving in the expected direction today.
    # ================================================
    day_change_pct = ctx.get("day_change_pct", 0.0)
    open_type = ctx.get("open_type", "UNKNOWN")

    # True if today's intraday move has confirmed the directional bias
    bullish_day_confirmed = (
        day_change_pct > 0.5
        or open_type in ("GAP_UP", "STRONG_GAP_UP")
        or (open_type == "UNKNOWN")   # no data → don't block
    )
    bearish_day_confirmed = (
        day_change_pct < -0.5
        or open_type in ("GAP_DOWN", "STRONG_GAP_DOWN")
        or (open_type == "UNKNOWN")   # no data → don't block
    )

    # ================================================
    # QUALITY GATE
    # ================================================
    if quality_score < 4:
        return "NO_TRADE", f"Insufficient quality score ({quality_score}/8 - minimum 4 required)"

    take_bull = bias == "BULLISH"
    take_bear = bias == "BEARISH"

    # Confidence thresholds (minimum 65% for all trades)
    spread_min_conf = max(65, min_confidence)
    if iv_regime == "LOW":
        spread_min_conf = max(65, min_confidence - 5)
    elif iv_regime == "NORMAL":
        spread_min_conf = max(65, min_confidence)

    # Ratio strategies require stronger conviction
    ratio_min_conf = max(65, min_confidence)
    ratio_quality_min = 6

    # ================================================
    # BREAKOUT / STRONG TREND → RATIO BACKSPREADS OR LONG STRADDLE/STRANGLE
    # ================================================
    if market_mode in ["TRENDING", "BREAKOUT_SETUP"]:
        # Strong directional conviction + low/normal IV → Ratio Backspreads
        # Also require that today's price action has CONFIRMED the directional move
        # (flat/neutral open after a strong prior-day move is NOT confirmation).
        if (
            adx >= 20
            and iv_regime in ["LOW", "NORMAL"]
            and confidence >= ratio_min_conf
            and quality_score >= ratio_quality_min
        ):
            if take_bull and bullish_day_confirmed:
                return (
                    "CALL_RATIO_BACKSPREAD",
                    f"Strong bullish move expected (ADX={adx:.1f}, IV={iv_regime}, conf={confidence:.0f}%, day={day_change_pct:+.2f}%)",
                )
            if take_bear and bearish_day_confirmed:
                return (
                    "PUT_RATIO_BACKSPREAD",
                    f"Strong bearish move expected (ADX={adx:.1f}, IV={iv_regime}, conf={confidence:.0f}%, day={day_change_pct:+.2f}%)",
                )

            # Indicators show directional bias but today's price action has NOT confirmed it
            # (e.g., flat open after yesterday's strong move). Downgrade to a safer spread.
            if take_bull and not bullish_day_confirmed:
                return (
                    "BULL_PUT",
                    f"Bullish TA but flat/weak open ({day_change_pct:+.2f}% today, open_type={open_type}) — waiting for day move to confirm; using safer spread",
                )
            if take_bear and not bearish_day_confirmed:
                return (
                    "BEAR_CALL",
                    f"Bearish TA but flat/weak open ({day_change_pct:+.2f}% today, open_type={open_type}) — waiting for day move to confirm; using safer spread",
                )
        
        # Expecting volatility spike (low IV currently) + no strong directional bias
        if iv_regime == "LOW" and confidence < 60 and quality_score >= 5:
            # Neutral/uncertain direction but expect big move → Long Straddle/Strangle
            return (
                "LONG_STRANGLE",
                f"Expecting volatility spike without clear direction (IV={iv_regime}, conf={confidence:.0f}%)"
            )

        # Fallback inside trend → safer spreads
        if confidence >= spread_min_conf:
            if take_bull:
                return "BULL_PUT", f"Trending bullish but breakout not strong enough (ADX={adx:.1f})"
            if take_bear:
                return "BEAR_CALL", f"Trending bearish but breakout not strong enough (ADX={adx:.1f})"

        return "NO_TRADE", "Trend present but conviction insufficient"

    # ================================================
    # RANGE + HIGH IV → PREMIUM SELLING STRATEGIES
    # ================================================
    if market_mode == "RANGE" and iv_regime == "HIGH":
        # VERY HIGH CONFIDENCE → SHORT STRADDLE (aggressive)
        if quality_score >= 6 and confidence >= 80:
            return (
                "SHORT_STRADDLE",
                f"Very high confidence range-bound with high IV (conf={confidence:.0f}%, qual={quality_score}/8)"
            )
        
        # HIGH CONFIDENCE → SHORT STRANGLE (less aggressive)
        if quality_score >= 6 and confidence >= 75:
            return (
                "SHORT_STRANGLE",
                f"High confidence range-bound with high IV (conf={confidence:.0f}%, qual={quality_score}/8)"
            )
        
        # MODERATE CONFIDENCE → IRON CONDOR (defined risk)
        if quality_score >= 5:
            return "IRON_CONDOR", "Range-bound market with high IV"
        
        return "NO_TRADE", "Range + high IV but insufficient quality"

    # ================================================
    # RANGE + LOW/NORMAL IV → DIRECTIONAL SPREADS OR BUTTERFLY
    # ================================================
    if market_mode == "RANGE" and iv_regime in ["LOW", "NORMAL"]:
        # Directional bias with enough confidence → spreads first
        if confidence >= spread_min_conf:
            if take_bull:
                return "BULL_PUT", f"Range but bullish bias (conf={confidence:.0f}%)"
            if take_bear:
                return "BEAR_CALL", f"Range but bearish bias (conf={confidence:.0f}%)"

        # Weak directional bias (confidence 55-65) → still use spreads, lower bar
        if confidence >= 55 and quality_score >= 5:
            if take_bull:
                return "BULL_PUT", f"Range with moderate bullish bias (conf={confidence:.0f}%)"
            if take_bear:
                return "BEAR_CALL", f"Range with moderate bearish bias (conf={confidence:.0f}%)"

        # Truly neutral (no bias, low confidence) + days_to_expiry context needed
        # Butterfly only makes sense near expiry when pinning is likely
        # For intraday 15m system, prefer Iron Condor over Butterfly
        if confidence < 55 and quality_score >= 5:
            return (
                "IRON_CONDOR",
                f"Range-bound with neutral bias and low/normal IV — Iron Condor preferred over Butterfly for intraday (conf={confidence:.0f}%)"
            )

        return "NO_TRADE", "Range + low/normal IV without sufficient conviction"

    # ================================================
    # FALLBACK
    # ================================================
    return "NO_TRADE", f"Unfavorable structure (mode={market_mode}, iv={iv_regime})"
