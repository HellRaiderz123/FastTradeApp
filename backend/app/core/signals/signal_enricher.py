"""
signal_enricher.py
------------------
Enriches TA signal with external market data.

IMPORTANT DESIGN RULES:
- IV regime is computed ONCE (vix_iv_api)
- Enricher must NEVER re-derive IV regime
- India VIX is primary, VIX Rank is contextual only
"""

from typing import Dict, Any, Optional


def enrich_signal_with_iv(
    ta_signal: Dict[str, Any],
    *,
    india_vix: Optional[float] = None,
    vix_rank: Optional[float] = None,
    iv_regime: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Enrich TA signal with volatility context.

    Args:
        ta_signal: Output from TA engine
        india_vix: Current India VIX
        vix_rank: Historical VIX percentile (0–100)
        iv_regime: LOW | NORMAL | HIGH (already decided upstream)

    Returns:
        Enriched signal dict
    """

    enriched = ta_signal.copy()

    indicators = enriched.get("indicators", {}).copy()
    quality_checks = enriched.get("quality_checks", {}).copy()

    # =================================================
    # Indicators (pure data, no logic)
    # =================================================
    if india_vix is not None:
        indicators["india_vix"] = round(india_vix, 2)

    if vix_rank is not None:
        indicators["vix_rank"] = round(vix_rank, 2)

    # =================================================
    # IV Regime (authoritative, do NOT recompute)
    # =================================================
    if iv_regime is not None:
        enriched["iv_regime"] = iv_regime

        # Trade permissibility by regime
        if iv_regime == "LOW":
            quality_checks["iv_trade_ok"] = True   # spreads allowed, sizing handled elsewhere
        elif iv_regime == "NORMAL":
            quality_checks["iv_trade_ok"] = True
        elif iv_regime == "HIGH":
            quality_checks["iv_trade_ok"] = True
        else:
            quality_checks["iv_trade_ok"] = False

    # =================================================
    # Quality score (boolean count)
    # =================================================
    quality_score = sum(1 for v in quality_checks.values() if v)

    # =================================================
    # Trade readiness adjustment (light touch)
    # =================================================
    readiness_score = enriched.get("trade_readiness_score", 0)

    if iv_regime == "LOW":
        readiness_score -= 5     # mild caution only
    elif iv_regime == "HIGH":
        readiness_score += 5     # IC / premium selling edge

    readiness_score = max(0, min(100, readiness_score))

    # =================================================
    # Final merge
    # =================================================
    enriched["indicators"] = indicators
    enriched["quality_checks"] = quality_checks
    enriched["quality_score"] = quality_score
    enriched["trade_readiness_score"] = int(readiness_score)

    return enriched


def merge_signals(
    ta_signal: Dict[str, Any],
    ml_signal: Optional[Dict[str, Any]] = None,
    external_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Merge TA + ML + external context.
    Priority: ML > TA (only if confidence higher).
    """

    merged = ta_signal.copy()

    if external_data:
        merged = enrich_signal_with_iv(
            merged,
            india_vix=external_data.get("india_vix"),
            vix_rank=external_data.get("vix_rank"),
            iv_regime=external_data.get("iv_regime"),
        )

    if ml_signal and ml_signal.get("confidence", 0) > merged.get("confidence", 0):
        merged["signal"] = ml_signal.get("signal", merged["signal"])
        merged["confidence"] = ml_signal.get("confidence", merged.get("confidence"))
        merged["bias"] = ml_signal.get("bias", merged.get("bias"))
        merged["ml_override"] = True
    else:
        merged["ml_override"] = False

    return merged


def parse_ml_app_response(ml_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse external ML app response into internal signal format.
    """

    signal_map = {
        "BUY_CE": "BULLISH",
        "BUY_PE": "BEARISH",
        "NO_TRADE": "RANGE",
    }

    return {
        "signal": signal_map.get(ml_response.get("signal"), "RANGE"),
        "confidence": ml_response.get("confidence", 0),
        "reason": ml_response.get("reason", "ML model signal"),
        "bias": (
            "BULLISH" if ml_response.get("signal") == "BUY_CE"
            else "BEARISH" if ml_response.get("signal") == "BUY_PE"
            else "NEUTRAL"
        ),
        "iv_regime": ml_response.get("iv_regime"),
        "quality_checks": ml_response.get("quality_checks", {}),
        "quality_score": ml_response.get("quality_score", 0),
        "trade_readiness_score": ml_response.get("trade_readiness_score", 0),
        "indicators": ml_response.get("indicators", {}),
        "trend_score": ml_response.get("trend_score", 0),
    }
