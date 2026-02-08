"""
Timeframe Suggestions API
Provides intelligent timeframe recommendations based on stock volatility and market conditions
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict
import logging
from datetime import datetime, timedelta
import numpy as np

logger = logging.getLogger(__name__)

router = APIRouter()


async def calculate_atr_based_suggestions(symbol: str) -> List[Dict]:
    """
    Calculate timeframe suggestions based on ATR (Average True Range) volatility
    Higher volatility = suggest shorter timeframes for active trading
    Lower volatility = suggest longer timeframes for position trading
    """
    from app.db.models_candles import Candle15m
    from app.db.session import SessionLocal
    from sqlalchemy import desc
    
    db = SessionLocal()
    
    try:
        # Fetch recent 15m candles from database
        candles_15m = db.query(Candle15m).filter(
            Candle15m.symbol == symbol
        ).order_by(desc(Candle15m.timestamp)).limit(100).all()
        
        if not candles_15m:
            logger.warning(f"No candle data found for {symbol}, returning default suggestions")
            return get_default_suggestions()
        
        # Convert to list of dicts
        data_15m = [
            {
                'close': c.close,
                'high': c.high,
                'low': c.low,
                'open': c.open,
                'volume': c.volume,
                'timestamp': c.timestamp
            }
            for c in candles_15m
        ]
        
        suggestions = []
        
        # 1-minute timeframe - for scalping (high volatility only)
        if data_15m:
            # Calculate recent volatility from 15m data
            closes_15m = [c['close'] for c in data_15m[:20]]
            if len(closes_15m) > 1:
                volatility_15m = np.std(closes_15m) / np.mean(closes_15m) * 100
                
                if volatility_15m > 1.5:
                    suggestions.append({
                        "timeframe": "1m",
                        "score": min(95, int(volatility_15m * 30)),
                        "reason": f"High intraday volatility ({volatility_15m:.2f}%) ideal for scalping trades",
                        "suitability": "excellent" if volatility_15m > 2.0 else "good"
                    })
                else:
                    suggestions.append({
                        "timeframe": "1m",
                        "score": 45,
                        "reason": "Low volatility makes scalping less profitable",
                        "suitability": "poor"
                    })
        
        # 5-minute timeframe - for day trading
        if data_15m:
            closes_15m = [c['close'] for c in data_15m[:40]]
            if len(closes_15m) > 1:
                volatility = np.std(closes_15m) / np.mean(closes_15m) * 100
                trend_strength = calculate_trend_strength(closes_15m)
                
                score = int(50 + (volatility * 15) + (trend_strength * 25))
                score = min(100, max(30, score))
                
                suggestions.append({
                    "timeframe": "5m",
                    "score": score,
                    "reason": f"Good for day trading with {volatility:.2f}% volatility and {trend_strength:.1f} trend strength",
                    "suitability": "excellent" if score >= 80 else "good" if score >= 60 else "moderate"
                })
        
        # 15-minute timeframe - for intraday momentum
        if data_15m:
            closes = [c['close'] for c in data_15m]
            if len(closes) > 1:
                volatility = np.std(closes) / np.mean(closes) * 100
                trend_strength = calculate_trend_strength(closes)
                volume_trend = calculate_volume_trend(data_15m)
                
                score = int(60 + (volatility * 10) + (trend_strength * 20) + (volume_trend * 10))
                score = min(100, max(40, score))
                
                suggestions.append({
                    "timeframe": "15m",
                    "score": score,
                    "reason": f"Balanced for intraday momentum with clear {assess_trend(closes)} trend",
                    "suitability": "excellent" if score >= 75 else "good" if score >= 55 else "moderate"
                })
        
        # 1-hour timeframe - for swing trading (aggregate 15m data)
        if data_15m:
            closes = [c['close'] for c in data_15m[:48]]  # Approx last 12 hours
            if len(closes) > 1:
                trend_strength = calculate_trend_strength(closes)
                consistency = calculate_trend_consistency(closes)
                
                score = int(55 + (trend_strength * 30) + (consistency * 15))
                score = min(100, max(50, score))
                
                suggestions.append({
                    "timeframe": "1h",
                    "score": score,
                    "reason": f"Optimal for swing trading with {assess_trend(closes)} trend and {consistency:.0f}% consistency",
                    "suitability": "excellent" if score >= 85 else "good" if score >= 65 else "moderate"
                })
        
        # 1-day timeframe - for position trading
        if data_15m:
            closes = [c['close'] for c in data_15m]
            if len(closes) > 1:
                trend_strength = calculate_trend_strength(closes)
                long_term_trend = 'uptrend' if closes[0] > closes[-1] else 'downtrend'
                
                score = int(65 + (trend_strength * 25))
                score = min(100, max(55, score))
                
                suggestions.append({
                    "timeframe": "1d",
                    "score": score,
                    "reason": f"Suitable for position trading in a {long_term_trend}",
                    "suitability": "excellent" if score >= 80 else "good" if score >= 60 else "moderate"
                })
        
        # Sort by score descending
        suggestions.sort(key=lambda x: x['score'], reverse=True)
        
        return suggestions
        
    except Exception as e:
        logger.error(f"Error calculating timeframe suggestions: {e}")
        # Return default suggestions if calculation fails
        return get_default_suggestions()
    finally:
        db.close()


def calculate_trend_strength(prices: List[float]) -> float:
    """Calculate trend strength (0-1) based on linear regression R²"""
    if len(prices) < 2:
        return 0
    
    x = np.arange(len(prices))
    y = np.array(prices)
    
    # Linear regression
    coefficients = np.polyfit(x, y, 1)
    predicted = np.polyval(coefficients, x)
    
    # R² calculation
    ss_res = np.sum((y - predicted) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    
    if ss_tot == 0:
        return 0
    
    r_squared = 1 - (ss_res / ss_tot)
    return max(0, min(1, r_squared))


def calculate_trend_consistency(prices: List[float]) -> float:
    """Calculate how consistent the trend is (% of moves in same direction)"""
    if len(prices) < 2:
        return 0
    
    changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    positive_moves = sum(1 for c in changes if c > 0)
    negative_moves = sum(1 for c in changes if c < 0)
    
    total_moves = len(changes)
    consistency = max(positive_moves, negative_moves) / total_moves * 100 if total_moves > 0 else 0
    
    return consistency


def calculate_volume_trend(candles: List[Dict]) -> float:
    """Calculate volume trend (0-1) - increasing volume = 1, decreasing = 0"""
    if len(candles) < 2:
        return 0.5
    
    volumes = [c.get('volume', 0) for c in candles]
    if not volumes or all(v == 0 for v in volumes):
        return 0.5
    
    recent_avg = np.mean(volumes[:10]) if len(volumes) >= 10 else np.mean(volumes[:len(volumes)//2])
    older_avg = np.mean(volumes[10:]) if len(volumes) > 10 else np.mean(volumes[len(volumes)//2:])
    
    if older_avg == 0:
        return 0.5
    
    ratio = recent_avg / older_avg
    return min(1.0, max(0.0, (ratio - 0.5) / 1.0))


def assess_trend(prices: List[float]) -> str:
    """Assess trend direction"""
    if len(prices) < 2:
        return "sideways"
    
    first_third = np.mean(prices[:len(prices)//3])
    last_third = np.mean(prices[-len(prices)//3:])
    
    diff_pct = ((last_third - first_third) / first_third) * 100
    
    if diff_pct > 2:
        return "bullish"
    elif diff_pct < -2:
        return "bearish"
    else:
        return "sideways"


def get_default_suggestions() -> List[Dict]:
    """Return default timeframe suggestions when calculation fails"""
    return [
        {
            "timeframe": "15m",
            "score": 75,
            "reason": "Balanced timeframe for intraday momentum trades",
            "suitability": "good"
        },
        {
            "timeframe": "1h",
            "score": 80,
            "reason": "Optimal for swing trading with reduced noise",
            "suitability": "excellent"
        },
        {
            "timeframe": "1d",
            "score": 70,
            "reason": "Suitable for position trading and trend following",
            "suitability": "good"
        },
        {
            "timeframe": "5m",
            "score": 65,
            "reason": "Good for active day trading",
            "suitability": "good"
        }
    ]


@router.get("/timeframe-suggestions/{symbol}")
async def get_timeframe_suggestions(
    symbol: str,
):
    """
    Get intelligent timeframe suggestions for a stock based on:
    - Recent volatility (ATR)
    - Trend strength
    - Volume profile
    - Historical price patterns
    
    Returns ranked timeframe suggestions with scores and explanations.
    """
    try:
        symbol = symbol.upper()
        
        suggestions = await calculate_atr_based_suggestions(symbol)
        
        return {
            "symbol": symbol,
            "suggestions": suggestions,
            "total": len(suggestions),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in get_timeframe_suggestions: {e}")
        # Return default suggestions on error
        return {
            "symbol": symbol.upper(),
            "suggestions": get_default_suggestions(),
            "total": 4,
            "timestamp": datetime.now().isoformat(),
            "note": "Using default suggestions due to data unavailability"
        }
