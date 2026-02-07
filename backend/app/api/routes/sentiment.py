"""
Sentiment Analysis API
Market sentiment indicators: VIX, PCR, Advance/Decline, Fear & Greed
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import logging

from app.services.zerodha import KiteConnectService
from app.core.indicators.put_call_ratio import PutCallRatioAnalyzer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sentiment", tags=["sentiment"])

kite_service = KiteConnectService()
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
            vix_quote = kite_service.get_full_quote("INDIA VIX")
            vix_level = vix_quote.get("last_price", 16.0) if vix_quote else 16.0
            
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
            # Get NIFTY 50 index movement
            nifty_quote = kite_service.get_full_quote("NIFTY 50")
            
            if nifty_quote:
                ltp = nifty_quote.get("last_price", 0)
                prev_close = nifty_quote.get("ohlc", {}).get("close", 0)
                
                if prev_close > 0:
                    change_pct = ((ltp - prev_close) / prev_close) * 100
                    
                    # Momentum score based on daily change
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
    """
    Get VIX (India VIX) analysis and interpretation
    
    Returns:
        {
            "current": 15.8,
            "change": -0.5,
            "change_percent": -3.1,
            "interpretation": "LOW_VOLATILITY",
            "regime": "CALM",
            "implications": "...",
            "historical_percentile": 35,
            "timestamp": "2024-01-09T15:30:00"
        }
    """
    try:
        vix_quote = kite_service.get_full_quote("INDIA VIX")
        
        if not vix_quote:
            raise HTTPException(status_code=404, detail="VIX data not available")
        
        current_vix = vix_quote.get("last_price", 0)
        vix_ohlc = vix_quote.get("ohlc", {})
        prev_close = vix_ohlc.get("close", current_vix)
        
        change = current_vix - prev_close
        change_pct = (change / prev_close * 100) if prev_close > 0 else 0
        
        # VIX regime classification
        if current_vix < 12:
            regime = "VERY_CALM"
            interpretation = "VERY_LOW_VOLATILITY"
            implications = "Market complacency. Low options premiums. Risk of sudden spike."
        elif current_vix < 15:
            regime = "CALM"
            interpretation = "LOW_VOLATILITY"
            implications = "Stable market. Good for selling premium strategies."
        elif current_vix < 20:
            regime = "NORMAL"
            interpretation = "MODERATE_VOLATILITY"
            implications = "Average volatility. Balanced risk environment."
        elif current_vix < 25:
            regime = "ELEVATED"
            interpretation = "ELEVATED_VOLATILITY"
            implications = "Increased uncertainty. Higher options premiums."
        else:
            regime = "HIGH_STRESS"
            interpretation = "HIGH_VOLATILITY"
            implications = "Market fear. Ideal for buying premium strategies."
        
        # Mock historical percentile (in production, calculate from historical data)
        historical_percentile = 35
        
        return {
            "current": round(current_vix, 2),
            "change": round(change, 2),
            "change_percent": round(change_pct, 2),
            "interpretation": interpretation,
            "regime": regime,
            "implications": implications,
            "historical_percentile": historical_percentile,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error fetching VIX analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pcr")
async def get_pcr_analysis() -> Dict[str, Any]:
    """
    Get Put-Call Ratio analysis for NIFTY
    
    Returns:
        {
            "pcr": 0.85,
            "interpretation": "NEUTRAL_BULLISH",
            "put_oi": 8500000,
            "call_oi": 10000000,
            "implications": "...",
            "timestamp": "2024-01-09T15:30:00"
        }
    """
    try:
        # In production, calculate from actual option chain
        # For now, return mock PCR data
        pcr_value = 0.85
        put_oi = 8500000
        call_oi = 10000000
        
        if pcr_value < 0.7:
            interpretation = "BULLISH"
            implications = "More calls than puts. Strong bullish sentiment."
        elif pcr_value < 0.85:
            interpretation = "NEUTRAL_BULLISH"
            implications = "Slightly more calls. Moderately bullish outlook."
        elif pcr_value < 1.0:
            interpretation = "NEUTRAL"
            implications = "Balanced put-call distribution."
        elif pcr_value < 1.15:
            interpretation = "NEUTRAL_BEARISH"
            implications = "Slightly more puts. Cautiously bearish."
        else:
            interpretation = "BEARISH"
            implications = "More puts than calls. Strong bearish sentiment or hedging."
        
        return {
            "pcr": round(pcr_value, 2),
            "interpretation": interpretation,
            "put_oi": put_oi,
            "call_oi": call_oi,
            "implications": implications,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error calculating PCR: {e}")
        raise HTTPException(status_code=500, detail=str(e))
