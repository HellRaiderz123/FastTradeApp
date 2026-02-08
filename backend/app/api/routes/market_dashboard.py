"""
Market Dashboard API
Top movers, market breadth, heatmap data, sentiment indicators
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

from app.services.zerodha import KiteConnectService
from app.core.indicators.technical import TechnicalIndicators
from app.core.broker.zerodha.instruments import load_instruments
from app.config.market_config import get_symbols, get_all_sectors, SECTOR_CLASSIFICATION

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market-dashboard", tags=["market-dashboard"])

kite_service = KiteConnectService()


@router.get("/top-movers")
async def get_top_movers(
    limit: int = Query(default=10, ge=5, le=20),
    universe: str = Query(default="NIFTY50")
) -> Dict[str, Any]:
    """
    Get top gainers, losers, and most active stocks from specified universe
    
    Args:
        limit: Number of stocks per category
        universe: Market universe (e.g., "NIFTY50", "BANKNIFTY")
    
    Returns:
        {
            "gainers": [...],
            "losers": [...],
            "most_active": [...],
            "timestamp": "2024-01-09T15:30:00"
        }
    """
    try:
        # Get symbols from config
        symbols = get_symbols(universe)
        
        # Fetch quotes for all stocks
        quotes_data = {}
        
        # Fetch in batches (Zerodha has limits)
        batch_size = 50
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            try:
                batch_quotes = kite_service.get_bulk_quotes(batch)
                if batch_quotes:
                    quotes_data.update(batch_quotes)
            except Exception as e:
                logger.warning(f"Error fetching batch quotes: {e}")
        
        # If no quotes received, raise error
        if not quotes_data:
            logger.error("Failed to fetch quotes from Zerodha. Please ensure Zerodha is connected.")
            raise HTTPException(
                status_code=503,
                detail="Unable to fetch market data. Please ensure your Zerodha account is connected and has valid API credentials."
            )
        
        # Process quotes
        stocks = []
        for symbol in symbols:
            quote = quotes_data.get(f"NSE:{symbol}")
            if not quote:
                continue
            
            ltp = quote.get("last_price", 0)
            prev_close = quote.get("ohlc", {}).get("close", 0)
            volume = quote.get("volume", 0)
            
            if ltp == 0 or prev_close == 0:
                continue
            
            change_pct = ((ltp - prev_close) / prev_close) * 100
            
            stocks.append({
                "symbol": symbol,
                "ltp": round(ltp, 2),
                "change": round(ltp - prev_close, 2),
                "change_percent": round(change_pct, 2),
                "volume": volume,
                "prev_close": prev_close
            })
        
        # Sort for top movers
        gainers = sorted(stocks, key=lambda x: x["change_percent"], reverse=True)[:limit]
        losers = sorted(stocks, key=lambda x: x["change_percent"])[:limit]
        most_active = sorted(stocks, key=lambda x: x["volume"], reverse=True)[:limit]
        
        return {
            "gainers": gainers,
            "losers": losers,
            "most_active": most_active,
            "timestamp": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching top movers: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch top movers: {str(e)}"
        )


@router.get("/market-breadth")
async def get_market_breadth(
    universe: str = Query(default="NIFTY50")
) -> Dict[str, Any]:
    """
    Calculate market breadth indicators
    
    Args:
        universe: Market universe to analyze
    
    Returns:
        {
            "advancing": 32,
            "declining": 15,
            "unchanged": 3,
            "advance_decline_ratio": 2.13,
            "new_highs_52w": 8,
            "new_lows_52w": 2,
            "breadth_strength": "STRONG",
            "timestamp": "2024-01-09T15:30:00"
        }
    """
    try:
        # Get symbols from config
        symbols = get_symbols(universe)
        
        # Fetch quotes
        quotes_data = {}
        batch_quotes = kite_service.get_bulk_quotes(symbols)
        if batch_quotes:
            quotes_data = batch_quotes
        
        advancing = 0
        declining = 0
        unchanged = 0
        new_highs_52w = 0
        new_lows_52w = 0
        
        for symbol in symbols:
            quote = quotes_data.get(f"NSE:{symbol}")
            if not quote:
                continue
            
            ltp = quote.get("last_price", 0)
            prev_close = quote.get("ohlc", {}).get("close", 0)
            high_52w = quote.get("upper_circuit_limit", 0)  # Approximate
            low_52w = quote.get("lower_circuit_limit", 0)   # Approximate
            
            if ltp == 0 or prev_close == 0:
                continue
            
            # Advance/Decline count
            if ltp > prev_close:
                advancing += 1
            elif ltp < prev_close:
                declining += 1
            else:
                unchanged += 1
            
            # New highs/lows (approximate)
            if high_52w > 0 and ltp >= high_52w * 0.99:
                new_highs_52w += 1
            if low_52w > 0 and ltp <= low_52w * 1.01:
                new_lows_52w += 1
        
        # Calculate A/D ratio
        ad_ratio = advancing / declining if declining > 0 else 0
        
        # Breadth strength classification
        if ad_ratio > 2.0:
            breadth_strength = "STRONG"
        elif ad_ratio > 1.5:
            breadth_strength = "MODERATE"
        elif ad_ratio > 1.0:
            breadth_strength = "NEUTRAL"
        elif ad_ratio > 0.5:
            breadth_strength = "WEAK"
        else:
            breadth_strength = "VERY_WEAK"
        
        # If no data received, raise error
        total_stocks = advancing + declining + unchanged
        if total_stocks == 0:
            logger.error("No market breadth data available")
            raise HTTPException(
                status_code=503,
                detail="Unable to calculate market breadth. Please ensure Zerodha is connected and try again."
            )
        
        return {
            "advancing": advancing,
            "declining": declining,
            "unchanged": unchanged,
            "advance_decline_ratio": round(ad_ratio, 2),
            "new_highs_52w": new_highs_52w,
            "new_lows_52w": new_lows_52w,
            "breadth_strength": breadth_strength,
            "total_stocks": total_stocks,
            "timestamp": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating market breadth: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate market breadth: {str(e)}"
        )


@router.get("/heatmap")
async def get_heatmap_data(
    universe: str = Query(default="NIFTY50")
) -> Dict[str, Any]:
    """
    Get NIFTY 50 heatmap data with performance and volume
    
    Args:
        universe: Market universe to analyze
    
    Returns:
        {
            "stocks": [
                {
                    "symbol": "RELIANCE",
                    "change_percent": 1.23,
                    "volume": 5000000,
                    "volume_ratio": 1.8,
                    "market_cap_rank": 1
                },
                ...
            ],
            "timestamp": "2024-01-09T15:30:00"
        }
    """
    try:
        # Get symbols from config
        symbols = get_symbols(universe)
        
        # Fetch quotes
        quotes_data = {}
        batch_quotes = kite_service.get_bulk_quotes(symbols)
        if batch_quotes:
            quotes_data = batch_quotes
        
        heatmap_stocks = []
        
        for idx, symbol in enumerate(symbols):
            quote = quotes_data.get(f"NSE:{symbol}")
            if not quote:
                continue
            
            ltp = quote.get("last_price", 0)
            prev_close = quote.get("ohlc", {}).get("close", 0)
            volume = quote.get("volume", 0)
            avg_traded_price = quote.get("average_price", ltp)
            
            if ltp == 0 or prev_close == 0:
                continue
            
            change_pct = ((ltp - prev_close) / prev_close) * 100
            
            # Volume ratio (approximate - current vs typical)
            # In production, calculate from historical data
            volume_ratio = 1.0  # Placeholder
            
            heatmap_stocks.append({
                "symbol": symbol,
                "ltp": round(ltp, 2),
                "change_percent": round(change_pct, 2),
                "volume": volume,
                "volume_ratio": volume_ratio,
                "market_cap_rank": idx + 1,  # Based on NIFTY50 ordering
                "avg_price": round(avg_traded_price, 2)
            })
        
        # If no data received, raise error
        if not heatmap_stocks:
            logger.error("No heatmap data available")
            raise HTTPException(
                status_code=503,
                detail="Unable to fetch heatmap data. Please ensure Zerodha is connected and try again."
            )
        
        return {
            "stocks": heatmap_stocks,
            "timestamp": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching heatmap data: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch heatmap data: {str(e)}"
        )


@router.get("/sector-performance")
async def get_sector_performance() -> Dict[str, Any]:
    """
    Calculate sector-wise performance
    
    Returns:
        {
            "sectors": [
                {
                    "name": "IT",
                    "change_percent": 1.5,
                    "stocks_count": 8,
                    "top_performers": ["TCS", "INFY"],
                    "strength": "STRONG"
                },
                ...
            ],
            "timestamp": "2024-01-09T15:30:00"
        }
    """
    try:
        # Get sector classification from config
        sectors = SECTOR_CLASSIFICATION
        all_symbols = []
        for stocks in sectors.values():
            all_symbols.extend(stocks)
        
        logger.info(f"Fetching sector performance for {len(all_symbols)} symbols across {len(sectors)} sectors")
        
        # Fetch quotes
        quotes_data = {}
        batch_quotes = kite_service.get_bulk_quotes(all_symbols)
        if batch_quotes:
            quotes_data = batch_quotes
            logger.info(f"Received {len(quotes_data)} quotes for sector analysis")
        else:
            logger.warning("No quotes received from Zerodha for sector performance")
        
        sector_results = []
        
        for sector_name, stocks in sectors.items():
            sector_changes = []
            stock_data = []
            
            for symbol in stocks:
                quote = quotes_data.get(f"NSE:{symbol}")
                if not quote:
                    continue
                
                ltp = quote.get("last_price", 0)
                prev_close = quote.get("ohlc", {}).get("close", 0)
                
                if ltp == 0 or prev_close == 0:
                    continue
                
                change_pct = ((ltp - prev_close) / prev_close) * 100
                sector_changes.append(change_pct)
                stock_data.append({
                    "symbol": symbol,
                    "change_percent": change_pct
                })
            
            if not sector_changes:
                continue
            
            avg_change = sum(sector_changes) / len(sector_changes)
            
            # Top performers in sector
            top_performers = sorted(stock_data, key=lambda x: x["change_percent"], reverse=True)[:2]
            
            # Sector strength
            if avg_change > 1.0:
                strength = "STRONG"
            elif avg_change > 0.3:
                strength = "MODERATE"
            elif avg_change > -0.3:
                strength = "NEUTRAL"
            elif avg_change > -1.0:
                strength = "WEAK"
            else:
                strength = "VERY_WEAK"
            
            sector_results.append({
                "name": sector_name,
                "change_percent": round(avg_change, 2),
                "stocks_count": len(stocks),
                "top_performers": [s["symbol"] for s in top_performers],
                "strength": strength
            })
        
        # Sort by performance (even if empty)
        sector_results.sort(key=lambda x: x["change_percent"], reverse=True)
        
        logger.info(f"Sector performance calculated: {len(sector_results)} sectors with data")
        
        return {
            "sectors": sector_results,
            "timestamp": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating sector performance: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate sector performance: {str(e)}"
        )


@router.get("/stock-technicals/{symbol}")
async def get_stock_technicals(symbol: str) -> Dict[str, Any]:
    """
    Get comprehensive technical analysis for a stock using REAL historical data
    
    Args:
        symbol: Stock symbol (e.g., "RELIANCE")
    
    Returns:
        {
            "symbol": "RELIANCE",
            "ltp": 2850.50,
            "indicators": {
                "rsi": 65.3,
                "macd": {...},
                "bollinger": {...},
                "adx": {...},
                "volume": {...}
            },
            "signal": "BULLISH",
            "trend": "UPTREND",
            "recommendation": "BUY",
            "timestamp": "2024-01-09T15:30:00"
        }
    """
    try:
        from app.core.data.candles import get_historical_candles
        
        symbol = symbol.upper()
        
        # Get real historical data (last 100 days of daily candles)
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=150)  # Get more data to be safe
        
        logger.info(f"📊 Fetching historical candles for {symbol} ({start_date} to {end_date})")
        
        # Try to get real candles
        candles = get_historical_candles(symbol, start_date, end_date, "daily")
        
        if not candles or len(candles) < 20:
            logger.warning(f"⚠️ Insufficient candle data for {symbol} (got {len(candles) if candles else 0})")
            
            # Get current quote at least
            quote = kite_service.get_full_quote(symbol)
            if not quote:
                raise HTTPException(status_code=404, detail=f"Quote not found for {symbol}")
            
            ltp = quote.get("last_price", 0)
            return {
                "symbol": symbol,
                "ltp": round(ltp, 2),
                "indicators": {
                    "rsi": None,
                    "macd": None,
                    "bollinger": None,
                    "adx": None,
                    "volume": None
                },
                "swing_pattern": None,
                "signal": "NEUTRAL",
                "trend": "INSUFFICIENT_DATA",
                "recommendation": "HOLD",
                "timestamp": datetime.now().isoformat()
            }
        
        # Extract OHLCV from candles
        closes = [c.get("close", c.get("price", 0)) for c in candles]
        highs = [c.get("high", c.get("price", 0)) for c in candles]
        lows = [c.get("low", c.get("price", 0)) for c in candles]
        volumes = [c.get("volume", 0) for c in candles]
        ltp = closes[-1] if closes else 0
        
        logger.info(f"✅ Got {len(candles)} candles for {symbol}, calculating indicators...")
        
        # Calculate indicators from REAL data
        indicators = {
            "rsi": TechnicalIndicators.calculate_rsi(closes, 14),
            "macd": TechnicalIndicators.calculate_macd(closes),
            "bollinger": TechnicalIndicators.calculate_bollinger_bands(closes),
            "adx": TechnicalIndicators.calculate_adx(highs, lows, closes),
            "volume": TechnicalIndicators.calculate_volume_analysis(volumes, closes)
        }
        
        # Detect swing patterns
        swing_pattern = TechnicalIndicators.detect_swing_pattern(closes, volumes, highs, lows)
        
        # Determine trend (comparing recent vs older price)
        if len(closes) >= 50:
            recent_avg = sum(closes[-20:]) / min(20, len(closes))
            older_avg = sum(closes[-50:-30]) / 20 if len(closes) >= 50 else sum(closes[:20]) / min(20, len(closes))
            
            if older_avg > 0:
                trend = "UPTREND" if recent_avg > older_avg else "DOWNTREND"
            else:
                trend = "SIDEWAYS"
        else:
            trend = "SIDEWAYS"
        
        # Get recommendation based on indicators
        rsi = indicators.get("rsi")
        adx_data = indicators.get("adx")
        adx_val = adx_data.get("adx") if adx_data else None
        
        if rsi is None:
            recommendation = "HOLD"
        elif rsi > 70:
            recommendation = "SELL"
        elif rsi < 30:
            recommendation = "BUY"
        elif adx_val and adx_val > 25:
            recommendation = "BUY" if trend == "UPTREND" else "SELL"
        else:
            recommendation = "HOLD"
        
        logger.info(f"✅ Technicals calculated for {symbol}: RSI={rsi}, ADX={adx_val}, Trend={trend}")
        
        return {
            "symbol": symbol,
            "ltp": round(ltp, 2),
            "indicators": indicators,
            "swing_pattern": swing_pattern,
            "signal": swing_pattern.get("signal", "NEUTRAL") if swing_pattern else "NEUTRAL",
            "trend": trend,
            "recommendation": recommendation,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"❌ Error calculating technicals for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
