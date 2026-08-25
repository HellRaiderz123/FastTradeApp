"""
decision.py
------------
Pure strategy-decision logic.
Decides WHAT strategy to take, not HOW.

Key principles for profitability:
1. SELL premium in HIGH IV (theta works for you)
2. BUY premium in LOW IV only with strong directional conviction
3. Use mean-reversion signals (oversold/overbought) for directional spreads
4. Avoid premium selling in LOW IV (poor risk/reward)
5. Require OI/PCR confirmation for directional trades
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
    """

    bias = ctx.get("bias", "NEUTRAL")
    market_mode = ctx.get("market_mode")
    iv_regime = ctx.get("iv_regime")
    quality_score = ctx.get("quality_score", 0)
    indicators = ctx.get("indicators", {})

    adx = float(indicators.get("adx", 0))
    rsi = float(indicators.get("rsi", 50))
    stoch_k = float(indicators.get("stoch_k", 50))
    pcr = float(indicators.get("option_pcr", 1.0) or 1.0)

    day_change_pct = float(ctx.get("day_change_pct", 0.0))
    open_type = ctx.get("open_type", "UNKNOWN")

    # OI confirmation from option chain
    oi_confirm = ctx.get("quality_checks", {}).get("oi_bias_confirm", True)

    # ================================================
    # MEAN REVERSION DETECTION (key for profitability)
    # Oversold/overbought extremes often precede reversals
    # ================================================
    deeply_oversold = rsi <= 35 and stoch_k <= 20
    deeply_overbought = rsi >= 65 and stoch_k >= 80
    moderately_oversold = rsi <= 40 and stoch_k <= 30
    moderately_overbought = rsi >= 60 and stoch_k >= 70

    # PCR extremes (contrarian signals)
    pcr_bullish = pcr >= 1.2  # High put buying = potential bottom
    pcr_bearish = pcr <= 0.6  # High call buying = potential top

    # Day confirmation
    bullish_day_confirmed = (
        day_change_pct > 0.3
        or open_type in ("GAP_UP", "STRONG_GAP_UP")
        or (open_type == "UNKNOWN")
    )
    bearish_day_confirmed = (
        day_change_pct < -0.3
        or open_type in ("GAP_DOWN", "STRONG_GAP_DOWN")
        or (open_type == "UNKNOWN")
    )

    # ================================================
    # QUALITY GATE (relaxed for high-probability setups)
    # ================================================
    base_quality_ok = quality_score >= 4
    high_quality = quality_score >= 6

    # ================================================
    # 1. HIGH IV REGIME → PREMIUM SELLING (best edge)
    # This is where option sellers make money
    # ================================================
    if iv_regime == "HIGH":
        # RANGE + HIGH IV = ideal for premium selling
        if market_mode == "RANGE":
            if high_quality and confidence >= 70:
                return (
                    "SHORT_STRANGLE",
                    f"HIGH IV + RANGE = premium selling edge (VIX elevated, conf={confidence:.0f}%)"
                )
            if base_quality_ok:
                return (
                    "IRON_CONDOR",
                    f"HIGH IV + RANGE = defined-risk premium collection (conf={confidence:.0f}%)"
                )

        # TRENDING + HIGH IV + directional bias → directional spreads
        if market_mode in ["TRENDING", "BREAKOUT_SETUP"]:
            if bias == "BULLISH" and confidence >= 60 and oi_confirm:
                return (
                    "BULL_PUT",
                    f"HIGH IV + bullish trend = sell puts for premium (ADX={adx:.1f}, conf={confidence:.0f}%)"
                )
            if bias == "BEARISH" and confidence >= 60 and oi_confirm:
                return (
                    "BEAR_CALL",
                    f"HIGH IV + bearish trend = sell calls for premium (ADX={adx:.1f}, conf={confidence:.0f}%)"
                )
            # No clear direction but high IV → still sell premium
            if base_quality_ok:
                return (
                    "IRON_CONDOR",
                    f"HIGH IV but unclear direction = wide Iron Condor (ADX={adx:.1f})"
                )

        return "NO_TRADE", f"HIGH IV but unfavorable setup (mode={market_mode}, qual={quality_score})"

    # ================================================
    # 2. NORMAL IV REGIME → BALANCED APPROACH
    # ================================================
    if iv_regime == "NORMAL":
        # MEAN REVERSION SETUPS (high probability)
        if deeply_oversold and (pcr_bullish or oi_confirm):
            if bullish_day_confirmed or day_change_pct > -0.8:
                return (
                    "BULL_PUT",
                    f"Oversold bounce setup (RSI={rsi:.1f}, Stoch={stoch_k:.1f}, PCR={pcr:.2f})"
                )
        if deeply_overbought and (pcr_bearish or oi_confirm):
            if bearish_day_confirmed or day_change_pct < 0.8:
                return (
                    "BEAR_CALL",
                    f"Overbought pullback setup (RSI={rsi:.1f}, Stoch={stoch_k:.1f}, PCR={pcr:.2f})"
                )

        # TRENDING with confirmation
        if market_mode in ["TRENDING", "BREAKOUT_SETUP"] and adx >= 22:
            if bias == "BULLISH" and confidence >= 60 and oi_confirm:
                return (
                    "BULL_PUT",
                    f"Bullish trend confirmed (ADX={adx:.1f}, conf={confidence:.0f}%)"
                )
            if bias == "BEARISH" and confidence >= 60 and oi_confirm:
                return (
                    "BEAR_CALL",
                    f"Bearish trend confirmed (ADX={adx:.1f}, conf={confidence:.0f}%)"
                )

        # RANGE with moderate confidence → Iron Condor
        if market_mode == "RANGE" and base_quality_ok and confidence >= 50:
            return (
                "IRON_CONDOR",
                f"NORMAL IV + RANGE = balanced Iron Condor (conf={confidence:.0f}%)"
            )

        # Moderate oversold/overbought with directional bias
        if moderately_oversold and bias != "BEARISH" and base_quality_ok:
            return (
                "BULL_PUT",
                f"Moderate oversold with neutral/bullish bias (RSI={rsi:.1f})"
            )
        if moderately_overbought and bias != "BULLISH" and base_quality_ok:
            return (
                "BEAR_CALL",
                f"Moderate overbought with neutral/bearish bias (RSI={rsi:.1f})"
            )

        return "NO_TRADE", f"NORMAL IV but no clear edge (mode={market_mode}, bias={bias})"

    # ================================================
    # 3. LOW IV REGIME → BUY OPTIONS (cheap premium)
    # Options are cheap - ideal for directional buys & scalping
    # ================================================
    if iv_regime == "LOW":
        # Momentum detection for scalping
        strong_momentum_up = day_change_pct >= 0.5 and rsi >= 55
        strong_momentum_down = day_change_pct <= -0.5 and rsi <= 45

        # ------------------------------------------------
        # SCALPING: Quick momentum plays (tight SL, quick exit)
        # Best when price is moving with momentum
        # ------------------------------------------------
        if market_mode == "TRENDING" and adx >= 25:
            if strong_momentum_up and bias == "BULLISH":
                return (
                    "SCALP_CALL",
                    f"LOW IV scalp: momentum up (day={day_change_pct:+.1f}%, ADX={adx:.1f}, RSI={rsi:.1f})"
                )
            if strong_momentum_down and bias == "BEARISH":
                return (
                    "SCALP_PUT",
                    f"LOW IV scalp: momentum down (day={day_change_pct:+.1f}%, ADX={adx:.1f}, RSI={rsi:.1f})"
                )

        # ------------------------------------------------
        # NAKED BUYS: Directional conviction plays
        # Cheap options = limited risk, unlimited reward
        # ------------------------------------------------
        # Mean reversion bounce - buy calls on oversold
        if deeply_oversold and (pcr_bullish or oi_confirm):
            return (
                "LONG_CALL",
                f"LOW IV + oversold = cheap calls (RSI={rsi:.1f}, Stoch={stoch_k:.1f}, PCR={pcr:.2f})"
            )
        # Mean reversion drop - buy puts on overbought
        if deeply_overbought and (pcr_bearish or oi_confirm):
            return (
                "LONG_PUT",
                f"LOW IV + overbought = cheap puts (RSI={rsi:.1f}, Stoch={stoch_k:.1f}, PCR={pcr:.2f})"
            )

        # Strong trend with confirmation - ride the move
        if market_mode == "TRENDING" and adx >= 22 and confidence >= 60:
            if bias == "BULLISH" and bullish_day_confirmed:
                return (
                    "LONG_CALL",
                    f"LOW IV + bullish trend = buy calls (ADX={adx:.1f}, conf={confidence:.0f}%)"
                )
            if bias == "BEARISH" and bearish_day_confirmed:
                return (
                    "LONG_PUT",
                    f"LOW IV + bearish trend = buy puts (ADX={adx:.1f}, conf={confidence:.0f}%)"
                )

        # ------------------------------------------------
        # BREAKOUT: Volatility expansion expected
        # ------------------------------------------------
        if market_mode == "BREAKOUT_SETUP" and adx >= 20 and high_quality:
            if bias == "BULLISH" and confidence >= 65:
                return (
                    "LONG_CALL",
                    f"LOW IV + breakout setup = buy calls before expansion (ADX={adx:.1f})"
                )
            if bias == "BEARISH" and confidence >= 65:
                return (
                    "LONG_PUT",
                    f"LOW IV + breakout setup = buy puts before expansion (ADX={adx:.1f})"
                )

        # Moderate setups with directional bias
        if moderately_oversold and bias != "BEARISH" and base_quality_ok:
            return (
                "LONG_CALL",
                f"LOW IV + moderate oversold = speculative call buy (RSI={rsi:.1f})"
            )
        if moderately_overbought and bias != "BULLISH" and base_quality_ok:
            return (
                "LONG_PUT",
                f"LOW IV + moderate overbought = speculative put buy (RSI={rsi:.1f})"
            )

        # No clear setup - still avoid (preserve capital)
        return "NO_TRADE", f"LOW IV but no clear directional setup (ADX={adx:.1f}, RSI={rsi:.1f})"

    # ================================================
    # FALLBACK
    # ================================================
    return "NO_TRADE", f"Unfavorable structure (mode={market_mode}, iv={iv_regime})"
