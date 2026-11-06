"""
Sentiment Analysis API
Market sentiment indicators: VIX, PCR, Advance/Decline, Fear & Greed
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import logging

from app.core.indicators.put_call_ratio import PutCallRatioAnalyzer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sentiment", tags=["sentiment"])

pcr_analyzer = PutCallRatioAnalyzer()


@router.get("/overall")
async def get_overall_sentiment() -> Dict[str, Any]:
    """
    Get comprehensive market sentiment analysis
    
    Returns:
        {
            "sentiment_score": 65,  # 0-100 scale
            "sentiment": "BULLISH",
            "vix_level": 15.8,
            "vix_interpretation": "LOW_VOLATILITY",
            "pcr": 0.85,
            "pcr_interpretation": "NEUTRAL_BULLISH",
            "advance_decline": 2.1,
            "breadth_strength": "STRONG",
            "fear_greed_index": 72,
            "components": {...},
            "timestamp": "2024-01-09T15:30:00"
        }
    """
    try:
        sentiment_components = {}
        total_score = 0
        weights = {}
        
        # 1. VIX Analysis (30% weight)
        try:
            from app.api.routes.nse_data import get_vix as _nse_get_vix
            nse_vix = await _nse_get_vix()
            vix_level = float(nse_vix.get("current") or 16.0)
            
            # VIX interpretation
            if vix_level < 12:
                vix_interpretation = "VERY_LOW_VOLATILITY"
                vix_score = 80  # Complacent, potentially risky
            elif vix_level < 15:
                vix_interpretation = "LOW_VOLATILITY"
                vix_score = 70
            elif vix_level < 20:
                vix_interpretation = "MODERATE_VOLATILITY"
                vix_score = 50
            elif vix_level < 25:
                vix_interpretation = "ELEVATED_VOLATILITY"
                vix_score = 30
            else:
                vix_interpretation = "HIGH_VOLATILITY"
                vix_score = 15  # Fear, potentially oversold
            
            sentiment_components["vix"] = {
                "level": round(vix_level, 2),
                "interpretation": vix_interpretation,
                "score": vix_score
            }
            
            weights["vix"] = 0.30
            total_score += vix_score * 0.30
            
        except Exception as e:
            logger.warning(f"Error fetching VIX: {e}")
            sentiment_components["vix"] = None
        
        # 2. Put-Call Ratio Analysis (25% weight)
        try:
            # Fetch NIFTY options data for PCR calculation
            # In production, calculate from actual option chain
            # For now, use mock PCR
            pcr_value = 0.85  # Mock value
            
            if pcr_value < 0.7:
                pcr_interpretation = "BULLISH"
                pcr_score = 75
            elif pcr_value < 0.85:
                pcr_interpretation = "NEUTRAL_BULLISH"
                pcr_score = 60
            elif pcr_value < 1.0:
                pcr_interpretation = "NEUTRAL"
                pcr_score = 50
            elif pcr_value < 1.15:
                pcr_interpretation = "NEUTRAL_BEARISH"
                pcr_score = 40
            else:
                pcr_interpretation = "BEARISH"
                pcr_score = 25
            
            sentiment_components["pcr"] = {
                "value": round(pcr_value, 2),
                "interpretation": pcr_interpretation,
                "score": pcr_score
            }
            
            weights["pcr"] = 0.25
            total_score += pcr_score * 0.25
            
        except Exception as e:
            logger.warning(f"Error calculating PCR: {e}")
            sentiment_components["pcr"] = None
        
        # 3. Advance/Decline Ratio (25% weight)
        try:
            # Fetch from market breadth endpoint
            from app.api.routes.market_dashboard import get_market_breadth
            breadth_data = await get_market_breadth()
            
            ad_ratio = breadth_data.get("advance_decline_ratio", 1.0)
            
            if ad_ratio > 2.0:
                ad_score = 85
                breadth_strength = "VERY_STRONG"
            elif ad_ratio > 1.5:
                ad_score = 70
                breadth_strength = "STRONG"
            elif ad_ratio > 1.0:
                ad_score = 55
                breadth_strength = "NEUTRAL_POSITIVE"
            elif ad_ratio > 0.7:
                ad_score = 40
                breadth_strength = "NEUTRAL_NEGATIVE"
            else:
                ad_score = 20
                breadth_strength = "WEAK"
            
            sentiment_components["advance_decline"] = {
                "ratio": round(ad_ratio, 2),
                "advancing": breadth_data.get("advancing", 0),
                "declining": breadth_data.get("declining", 0),
                "strength": breadth_strength,
                "score": ad_score
            }
            
            weights["advance_decline"] = 0.25
            total_score += ad_score * 0.25
            
        except Exception as e:
            logger.warning(f"Error fetching A/D ratio: {e}")
            sentiment_components["advance_decline"] = None
        
        # 4. Price Momentum (20% weight)
        try:
            from app.core.market.provider import fetch_ltp
            prices = fetch_ltp(["NIFTY"])
            ltp = float(prices.get("NIFTY") or 0)
            if ltp > 0:
                change_pct = 0.0  # no prev close from LTP-only; treat as flat
                if change_pct > 1.0:
                    momentum_score = 80
                    momentum_state = "STRONG_BULLISH"
                elif change_pct > 0.3:
                    momentum_score = 65
                    momentum_state = "BULLISH"
                elif change_pct > -0.3:
                    momentum_score = 50
                    momentum_state = "NEUTRAL"
                elif change_pct > -1.0:
                    momentum_score = 35
                    momentum_state = "BEARISH"
                else:
                    momentum_score = 20
                    momentum_state = "STRONG_BEARISH"
                sentiment_components["momentum"] = {
                    "nifty_change_percent": round(change_pct, 2),
                    "state": momentum_state,
                    "score": momentum_score
                }
                weights["momentum"] = 0.20
                total_score += momentum_score * 0.20
            else:
                sentiment_components["momentum"] = None
        except Exception as e:
            logger.warning(f"Error calculating momentum: {e}")
            sentiment_components["momentum"] = None
        
        # Calculate overall sentiment
        overall_score = round(total_score, 0)
        
        # Interpret overall sentiment
        if overall_score >= 70:
            overall_sentiment = "BULLISH"
        elif overall_score >= 55:
            overall_sentiment = "NEUTRAL_BULLISH"
        elif overall_score >= 45:
            overall_sentiment = "NEUTRAL"
        elif overall_score >= 30:
            overall_sentiment = "NEUTRAL_BEARISH"
        else:
            overall_sentiment = "BEARISH"
        
        # Fear & Greed Index (composite)
        fear_greed_index = round(overall_score, 0)
        
        if fear_greed_index >= 75:
            fg_interpretation = "EXTREME_GREED"
        elif fear_greed_index >= 55:
            fg_interpretation = "GREED"
        elif fear_greed_index >= 45:
            fg_interpretation = "NEUTRAL"
        elif fear_greed_index >= 25:
            fg_interpretation = "FEAR"
        else:
            fg_interpretation = "EXTREME_FEAR"
        
        return {
            "sentiment_score": overall_score,
            "sentiment": overall_sentiment,
            "fear_greed_index": fear_greed_index,
            "fear_greed_interpretation": fg_interpretation,
            "components": sentiment_components,
            "weights": weights,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error calculating overall sentiment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vix")
async def get_vix_analysis() -> Dict[str, Any]:
    """Get VIX (India VIX) analysis — fetched from NSE with real prev_close for change."""
    try:
        # Delegate to nse_data which fetches real VIX from NSE allIndices
        from app.api.routes.nse_data import get_vix as _nse_get_vix
        nse_result = await _nse_get_vix()

        current_vix = nse_result.get("current")
        if not current_vix:
            raise HTTPException(status_code=404, detail="VIX data not available")

        # NSE allIndices provides previousClose — extract it for real change
        prev_close = nse_result.get("prev_close") or current_vix
        change = round(current_vix - prev_close, 2)
        change_pct = round((change / prev_close * 100) if prev_close > 0 else 0, 2)

        regime = nse_result.get("regime", "NORMAL")
        implications = nse_result.get("implications", "")

        if current_vix < 12:
            interpretation = "VERY_LOW_VOLATILITY"
        elif current_vix < 15:
            interpretation = "LOW_VOLATILITY"
        elif current_vix < 20:
            interpretation = "MODERATE_VOLATILITY"
        elif current_vix < 25:
            interpretation = "ELEVATED_VOLATILITY"
        else:
            interpretation = "HIGH_VOLATILITY"

        return {
            "current": round(current_vix, 2),
            "change": change,
            "change_percent": change_pct,
            "interpretation": interpretation,
            "regime": regime,
            "implications": implications,
            "historical_percentile": 35,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching VIX analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pcr")
async def get_pcr_analysis() -> Dict[str, Any]:
    """Get Put-Call Ratio from real NIFTY option chain (OI-based, volume fallback)."""
    try:
        from app.api.routes.options_real import get_real_option_chain
        chain = await get_real_option_chain("NIFTY")

        strikes = chain.get("strikes") or []
        call_oi = sum((s.get("call") or {}).get("oi") or 0 for s in strikes)
        put_oi = sum((s.get("put") or {}).get("oi") or 0 for s in strikes)
        call_vol = sum((s.get("call") or {}).get("volume") or 0 for s in strikes)
        put_vol = sum((s.get("put") or {}).get("volume") or 0 for s in strikes)

        # OI-based PCR preferred; fall back to volume
        if call_oi > 0:
            pcr_value = round(put_oi / call_oi, 2)
            basis = "OI"
        elif call_vol > 0:
            pcr_value = round(put_vol / call_vol, 2)
            basis = "Volume"
        else:
            pcr_value = 0.0
            basis = "Unavailable"

        if pcr_value < 0.7:
            interpretation, implications = "BULLISH", "More calls than puts. Strong bullish sentiment."
        elif pcr_value < 0.85:
            interpretation, implications = "NEUTRAL_BULLISH", "Slightly more calls. Moderately bullish outlook."
        elif pcr_value < 1.0:
            interpretation, implications = "NEUTRAL", "Balanced put-call distribution."
        elif pcr_value < 1.15:
            interpretation, implications = "NEUTRAL_BEARISH", "Slightly more puts. Cautiously bearish."
        else:
            interpretation, implications = "BEARISH", "More puts than calls. Strong bearish sentiment or hedging."

        return {
            "pcr": pcr_value,
            "basis": basis,
            "interpretation": interpretation,
            "put_oi": put_oi,
            "call_oi": call_oi,
            "put_volume": put_vol,
            "call_volume": call_vol,
            "implications": implications,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error calculating PCR: {e}")
        raise HTTPException(status_code=500, detail=str(e))
