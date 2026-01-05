"""
signal_enricher.py
------------------
Enriches TA signal with external market data (from ML app, VIX API, IV APIs, etc).

Used to merge:
- TA signal (EMA, RSI, ADX, etc.)
- External IV data (IV Rank, IV Regime)
- External VIX data (India VIX, VIX)
- Optional ML predictions
"""

from typing import Dict, Any, Optional


def enrich_signal_with_iv(
    ta_signal: Dict[str, Any],
    iv_rank: Optional[float] = None,
    india_vix: Optional[float] = None,
    iv_regime: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Enriches TA signal with IV data.
    
    Args:
        ta_signal: Output from ta_signal_15m()
        iv_rank: IV Rank percentile (0-100)
        india_vix: Current India VIX value
        iv_regime: "LOW", "NORMAL", or "HIGH"
    
    Returns:
        Enhanced signal with IV data merged
    """
    
    enriched = ta_signal.copy()
    indicators = enriched.get("indicators", {}).copy()
    quality_checks = enriched.get("quality_checks", {}).copy()
    
    # ============================
    # Add IV Data
    # ============================
    if iv_rank is not None:
        indicators["iv_rank"] = round(iv_rank, 2)
        # Determine IV regime from IV rank if not provided
        if iv_regime is None:
            if iv_rank < 25:
                iv_regime = "LOW"
            elif iv_rank > 75:
                iv_regime = "HIGH"
            else:
                iv_regime = "NORMAL"
    
    if india_vix is not None:
        indicators["india_vix"] = round(india_vix, 2)
        # Check if VIX matches quality check
        quality_checks["vix_ok"] = 10 <= india_vix <= 20
    
    # Override IV regime if provided
    if iv_regime is not None:
        enriched["iv_regime"] = iv_regime
        # Adjust IV trade OK check based on regime
        if iv_regime == "LOW":
            quality_checks["iv_trade_ok"] = False  # Don't trade in low IV
        elif iv_regime == "NORMAL":
            quality_checks["iv_trade_ok"] = True
        else:  # HIGH IV
            quality_checks["iv_trade_ok"] = True
    
    # ============================
    # Recalculate Quality Score
    # ============================
    quality_score = sum([1 for v in quality_checks.values() if v])
    
    # ============================
    # Adjust Trade Readiness Score
    # ============================
    readiness_adjustment = 0
    if iv_regime == "LOW":
        readiness_adjustment = -10  # Lower readiness in low IV
    elif iv_regime == "HIGH":
        readiness_adjustment = +5   # Slight boost in high IV for IC
    
    new_readiness_score = enriched.get("trade_readiness_score", 0) + readiness_adjustment
    new_readiness_score = max(0, min(100, new_readiness_score))  # Clamp 0-100
    
    # ============================
    # Update Signal
    # ============================
    enriched["indicators"] = indicators
    enriched["quality_checks"] = quality_checks
    enriched["quality_score"] = quality_score
    enriched["trade_readiness_score"] = int(new_readiness_score)
    
    return enriched


def merge_signals(
    ta_signal: Dict[str, Any],
    ml_signal: Optional[Dict[str, Any]] = None,
    external_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Merges multiple signal sources into one comprehensive signal.
    
    Priority: ML > TA (if ML confidence higher)
    
    Args:
        ta_signal: TA output
        ml_signal: Optional ML model output
        external_data: Optional {iv_rank, india_vix, iv_regime, ...}
    
    Returns:
        Merged signal with all data
    """
    
    # Start with TA signal
    merged = ta_signal.copy()
    
    # Enrich with external market data if provided
    if external_data:
        merged = enrich_signal_with_iv(
            merged,
            iv_rank=external_data.get("iv_rank"),
            india_vix=external_data.get("india_vix"),
            iv_regime=external_data.get("iv_regime"),
        )
    
    # Use ML signal if provided AND confidence is higher
    if ml_signal and ml_signal.get("confidence", 0) > merged.get("confidence", 0):
        # Override main signal with ML
        merged["signal"] = ml_signal.get("signal", merged["signal"])
        merged["confidence"] = ml_signal.get("confidence", merged.get("confidence"))
        merged["bias"] = ml_signal.get("bias", merged.get("bias"))
        merged["ml_override"] = True
    else:
        merged["ml_override"] = False
    
    return merged


def parse_ml_app_response(ml_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parses response from external ML app and converts to standard signal format.
    
    ML App returns:
    {
        "signal": "BUY_CE" | "BUY_PE" | "NO_TRADE",
        "confidence": 85.0,
        "quality_checks": {...},
        "quality_score": 7,
        "trade_readiness_score": 75,
        "indicators": {...},
        "iv_regime": "LOW",
        "india_vix": 10.1,
        "iv_rank": 7.26,
        ...
    }
    
    Converts to TA signal format.
    """
    
    signal_map = {
        "BUY_CE": "BULLISH",
        "BUY_PE": "BEARISH",
        "NO_TRADE": "RANGE",
    }
    
    return {
        "signal": signal_map.get(ml_response.get("signal", "NO_TRADE"), "RANGE"),
        "confidence": ml_response.get("confidence", 0),
        "reason": ml_response.get("reason", "ML model signal"),
        "bias": "BULLISH" if ml_response.get("signal") == "BUY_CE" else (
            "BEARISH" if ml_response.get("signal") == "BUY_PE" else "NEUTRAL"
        ),
        "iv_regime": ml_response.get("iv_regime", "NORMAL"),
        "quality_checks": ml_response.get("quality_checks", {}),
        "quality_score": ml_response.get("quality_score", 0),
        "trade_readiness_score": ml_response.get("trade_readiness_score", 0),
        "indicators": ml_response.get("indicators", {}),
        "trend_score": ml_response.get("trend_score", 0),
    }
