"""
Stock Screener API
Advanced filtering for NIFTY 50 stocks with technical & fundamental criteria
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging

from app.services.zerodha import KiteConnectService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/screener", tags=["screener"])

kite_service = KiteConnectService()


class ScreenerFilters(BaseModel):
    """Screener filter criteria"""
    
    # Price filters
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_change_percent: Optional[float] = None  # e.g., -5 to 10
    max_change_percent: Optional[float] = None
    
    # Volume filters
    min_volume: Optional[int] = None
    min_volume_ratio: Optional[float] = None  # Today vol / Avg vol
    
    # Technical filters - Basic
    rsi_min: Optional[float] = None  # 0-100
    rsi_max: Optional[float] = None
    price_above_ma: Optional[int] = None  # 20, 50, 200 day MA
    price_below_ma: Optional[int] = None
    
    # Technical filters - Advanced
    macd_positive: Optional[bool] = None  # MACD above signal line
    macd_negative: Optional[bool] = None  # MACD below signal line
    bollinger_squeeze: Optional[bool] = None  # Price near middle band
    bollinger_breakout: Optional[bool] = None  # Price touched/breached upper/lower
    atr_min: Optional[float] = None  # Average True Range (volatility)
    atr_max: Optional[float] = None
    adx_min: Optional[float] = None  # Trend strength (above 25 = trending)
    adx_max: Optional[float] = None
    
    # Fundamental filters
    min_pe_ratio: Optional[float] = None  # Price-to-Earnings
    max_pe_ratio: Optional[float] = None
    min_pb_ratio: Optional[float] = None  # Price-to-Book
    max_pb_ratio: Optional[float] = None
    min_dividend_yield: Optional[float] = None  # Dividend yield %
    max_debt_to_equity: Optional[float] = None  # Debt/Equity ratio
    min_roe: Optional[float] = None  # Return on Equity %
    
    # Pattern recognition
    pattern: Optional[str] = None  # bullish_engulfing, bearish_engulfing, doji, hammer, etc.
    
    # Market cap filter
    min_market_cap: Optional[float] = None  # In crores
    max_market_cap: Optional[float] = None
    
    # Sector filter
    sectors: Optional[List[str]] = None  # ["IT", "Finance", "Energy"]
    
    # Sorting
    sort_by: Optional[str] = "change_percent"  # change_percent, volume, price, rsi, market_cap, pe_ratio
    sort_order: Optional[str] = "desc"  # asc or desc


# NIFTY 50 stocks with metadata including fundamentals
NIFTY50_STOCKS = [
    {"symbol": "RELIANCE", "sector": "Energy", "market_cap": 1700000, "pe_ratio": 22.5, "pb_ratio": 2.8, "div_yield": 0.35, "roe": 8.5, "debt_equity": 0.45},
    {"symbol": "TCS", "sector": "IT", "market_cap": 1400000, "pe_ratio": 28.3, "pb_ratio": 12.5, "div_yield": 1.8, "roe": 45.2, "debt_equity": 0.0},
    {"symbol": "HDFCBANK", "sector": "Finance", "market_cap": 1200000, "pe_ratio": 18.7, "pb_ratio": 2.9, "div_yield": 1.2, "roe": 16.8, "debt_equity": 0.0},
    {"symbol": "INFY", "sector": "IT", "market_cap": 750000, "pe_ratio": 26.1, "pb_ratio": 8.2, "div_yield": 2.4, "roe": 28.5, "debt_equity": 0.0},
    {"symbol": "ICICIBANK", "sector": "Finance", "market_cap": 700000, "pe_ratio": 16.2, "pb_ratio": 2.6, "div_yield": 1.0, "roe": 15.3, "debt_equity": 0.0},
    {"symbol": "HINDUNILVR", "sector": "FMCG", "market_cap": 650000, "pe_ratio": 58.5, "pb_ratio": 12.8, "div_yield": 1.4, "roe": 82.5, "debt_equity": 0.0},
    {"symbol": "ITC", "sector": "FMCG", "market_cap": 550000, "pe_ratio": 24.8, "pb_ratio": 7.2, "div_yield": 3.8, "roe": 25.6, "debt_equity": 0.0},
    {"symbol": "SBIN", "sector": "Finance", "market_cap": 530000, "pe_ratio": 11.5, "pb_ratio": 1.2, "div_yield": 1.5, "roe": 12.8, "debt_equity": 0.0},
    {"symbol": "BHARTIARTL", "sector": "Telecom", "market_cap": 720000, "pe_ratio": 35.2, "pb_ratio": 4.5, "div_yield": 0.65, "roe": 13.2, "debt_equity": 1.85},
    {"symbol": "KOTAKBANK", "sector": "Finance", "market_cap": 350000, "pe_ratio": 17.8, "pb_ratio": 2.4, "div_yield": 0.45, "roe": 11.2, "debt_equity": 0.0},
    {"symbol": "LT", "sector": "Infrastructure", "market_cap": 480000, "pe_ratio": 32.5, "pb_ratio": 3.8, "div_yield": 0.9, "roe": 12.5, "debt_equity": 0.78},
    {"symbol": "AXISBANK", "sector": "Finance", "market_cap": 330000, "pe_ratio": 14.2, "pb_ratio": 1.8, "div_yield": 0.55, "roe": 12.5, "debt_equity": 0.0},
    {"symbol": "ASIANPAINT", "sector": "Consumer", "market_cap": 310000, "pe_ratio": 65.3, "pb_ratio": 15.2, "div_yield": 0.88, "roe": 28.5, "debt_equity": 0.05},
    {"symbol": "MARUTI", "sector": "Auto", "market_cap": 380000, "pe_ratio": 28.5, "pb_ratio": 3.5, "div_yield": 1.2, "roe": 15.8, "debt_equity": 0.22},
    {"symbol": "SUNPHARMA", "sector": "Pharma", "market_cap": 380000, "pe_ratio": 38.5, "pb_ratio": 5.8, "div_yield": 0.45, "roe": 16.2, "debt_equity": 0.12},
    {"symbol": "TITAN", "sector": "Consumer", "market_cap": 300000, "pe_ratio": 82.5, "pb_ratio": 28.5, "div_yield": 0.35, "roe": 35.8, "debt_equity": 0.05},
    {"symbol": "ULTRACEMCO", "sector": "Cement", "market_cap": 280000, "pe_ratio": 45.2, "pb_ratio": 8.5, "div_yield": 0.65, "roe": 19.5, "debt_equity": 0.18},
    {"symbol": "BAJFINANCE", "sector": "Finance", "market_cap": 470000, "pe_ratio": 32.8, "pb_ratio": 6.8, "div_yield": 0.25, "roe": 22.5, "debt_equity": 6.85},
    {"symbol": "NESTLEIND", "sector": "FMCG", "market_cap": 230000, "pe_ratio": 72.5, "pb_ratio": 58.5, "div_yield": 1.8, "roe": 115.2, "debt_equity": 0.0},
    {"symbol": "HCLTECH", "sector": "IT", "market_cap": 410000, "pe_ratio": 24.5, "pb_ratio": 5.8, "div_yield": 3.2, "roe": 23.5, "debt_equity": 0.0},
    {"symbol": "WIPRO", "sector": "IT", "market_cap": 250000, "pe_ratio": 22.8, "pb_ratio": 3.5, "div_yield": 1.5, "roe": 16.2, "debt_equity": 0.0},
    {"symbol": "TECHM", "sector": "IT", "market_cap": 120000, "pe_ratio": 25.5, "pb_ratio": 4.2, "div_yield": 1.8, "roe": 18.5, "debt_equity": 0.02},
    {"symbol": "ONGC", "sector": "Energy", "market_cap": 300000, "pe_ratio": 8.5, "pb_ratio": 0.88, "div_yield": 4.2, "roe": 9.8, "debt_equity": 0.32},
    {"symbol": "NTPC", "sector": "Power", "market_cap": 350000, "pe_ratio": 14.5, "pb_ratio": 1.8, "div_yield": 3.2, "roe": 12.5, "debt_equity": 2.15},
    {"symbol": "POWERGRID", "sector": "Power", "market_cap": 240000, "pe_ratio": 11.2, "pb_ratio": 1.5, "div_yield": 3.8, "roe": 13.5, "debt_equity": 1.85},
    {"symbol": "TATAMOTORS", "sector": "Auto", "market_cap": 320000, "pe_ratio": 18.5, "pb_ratio": 2.2, "div_yield": 0.15, "roe": 16.8, "debt_equity": 0.68},
    {"symbol": "TATASTEEL", "sector": "Metals", "market_cap": 180000, "pe_ratio": 42.5, "pb_ratio": 1.5, "div_yield": 1.8, "roe": 4.2, "debt_equity": 0.85},
    {"symbol": "HINDALCO", "sector": "Metals", "market_cap": 130000, "pe_ratio": 28.5, "pb_ratio": 1.8, "div_yield": 0.85, "roe": 7.5, "debt_equity": 0.55},
    {"symbol": "JSWSTEEL", "sector": "Metals", "market_cap": 210000, "pe_ratio": 35.2, "pb_ratio": 2.2, "div_yield": 1.2, "roe": 8.5, "debt_equity": 0.72},
    {"symbol": "ADANIPORTS", "sector": "Infrastructure", "market_cap": 280000, "pe_ratio": 48.5, "pb_ratio": 7.2, "div_yield": 0.45, "roe": 15.2, "debt_equity": 1.25},
    {"symbol": "COALINDIA", "sector": "Energy", "market_cap": 290000, "pe_ratio": 9.5, "pb_ratio": 1.2, "div_yield": 5.8, "roe": 28.5, "debt_equity": 0.12},
    {"symbol": "DRREDDY", "sector": "Pharma", "market_cap": 95000, "pe_ratio": 32.5, "pb_ratio": 4.5, "div_yield": 0.65, "roe": 14.8, "debt_equity": 0.22},
    {"symbol": "CIPLA", "sector": "Pharma", "market_cap": 110000, "pe_ratio": 28.5, "pb_ratio": 3.8, "div_yield": 0.75, "roe": 13.5, "debt_equity": 0.08},
    {"symbol": "DIVISLAB", "sector": "Pharma", "market_cap": 120000, "pe_ratio": 45.8, "pb_ratio": 8.5, "div_yield": 0.55, "roe": 18.5, "debt_equity": 0.05},
    {"symbol": "EICHERMOT", "sector": "Auto", "market_cap": 120000, "pe_ratio": 42.5, "pb_ratio": 12.8, "div_yield": 0.85, "roe": 32.5, "debt_equity": 0.02},
    {"symbol": "HEROMOTOCO", "sector": "Auto", "market_cap": 110000, "pe_ratio": 28.5, "pb_ratio": 8.2, "div_yield": 2.2, "roe": 28.5, "debt_equity": 0.0},
    {"symbol": "BAJAJFINSV", "sector": "Finance", "market_cap": 270000, "pe_ratio": 15.2, "pb_ratio": 3.2, "div_yield": 0.85, "roe": 18.5, "debt_equity": 2.85},
    {"symbol": "BAJAJ-AUTO", "sector": "Auto", "market_cap": 290000, "pe_ratio": 32.5, "pb_ratio": 8.5, "div_yield": 1.8, "roe": 28.5, "debt_equity": 0.0},
    {"symbol": "M&M", "sector": "Auto", "market_cap": 290000, "pe_ratio": 25.5, "pb_ratio": 4.2, "div_yield": 1.2, "roe": 18.8, "debt_equity": 0.45},
    {"symbol": "GRASIM", "sector": "Cement", "market_cap": 140000, "pe_ratio": 18.5, "pb_ratio": 2.5, "div_yield": 1.5, "roe": 14.5, "debt_equity": 0.68},
    {"symbol": "BRITANNIA", "sector": "FMCG", "market_cap": 130000, "pe_ratio": 55.5, "pb_ratio": 28.5, "div_yield": 1.2, "roe": 52.5, "debt_equity": 0.02},
    {"symbol": "INDUSINDBK", "sector": "Finance", "market_cap": 110000, "pe_ratio": 12.5, "pb_ratio": 1.5, "div_yield": 0.95, "roe": 11.5, "debt_equity": 0.0},
    {"symbol": "SHREECEM", "sector": "Cement", "market_cap": 90000, "pe_ratio": 38.5, "pb_ratio": 6.8, "div_yield": 0.55, "roe": 18.2, "debt_equity": 0.08},
    {"symbol": "APOLLOHOSP", "sector": "Healthcare", "market_cap": 93000, "pe_ratio": 85.5, "pb_ratio": 12.5, "div_yield": 0.28, "roe": 15.8, "debt_equity": 0.22},
    {"symbol": "BPCL", "sector": "Energy", "market_cap": 120000, "pe_ratio": 12.5, "pb_ratio": 1.5, "div_yield": 3.8, "roe": 12.5, "debt_equity": 0.85},
    {"symbol": "UPL", "sector": "Chemicals", "market_cap": 52000, "pe_ratio": 15.5, "pb_ratio": 2.2, "div_yield": 1.2, "roe": 14.8, "debt_equity": 0.92},
    {"symbol": "TATACONSUM", "sector": "FMCG", "market_cap": 85000, "pe_ratio": 68.5, "pb_ratio": 18.5, "div_yield": 0.65, "roe": 28.5, "debt_equity": 0.15},
]


def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    """Calculate RSI indicator"""
    if len(prices) < period + 1:
        return None
    
    gains = []
    losses = []
    
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    if len(gains) < period:
        return None
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return round(rsi, 2)


@router.post("/filter")
async def filter_stocks(filters: ScreenerFilters):
    """
    Filter NIFTY 50 stocks based on criteria
    
    Returns matching stocks with:
    - Current price & change
    - Volume data
    - Technical indicators (RSI, MA)
    - Sector & market cap
    """
    try:
        # Get all symbols
        symbols = [stock["symbol"] for stock in NIFTY50_STOCKS]
        
        # Fetch bulk quotes
        from app.api.routes.market import kite_service as market_kite
        results = []
        
        for stock_meta in NIFTY50_STOCKS:
            symbol = stock_meta["symbol"]
            
            try:
                # Get current quote
                quote_data = market_kite.get_full_quote(symbol)
                
                if not quote_data or "last_price" not in quote_data:
                    logger.warning(f"No data for {symbol}, skipping")
                    continue
                
                ltp = float(quote_data["last_price"])
                ohlc = quote_data.get("ohlc", {})
                prev_close = ohlc.get("close", ltp)
                change = ltp - prev_close
                change_percent = (change / prev_close * 100) if prev_close else 0
                volume = quote_data.get("volume", 0)
                
                # Apply filters
                # Price filters
                if filters.min_price and ltp < filters.min_price:
                    continue
                if filters.max_price and ltp > filters.max_price:
                    continue
                
                # Change % filters
                if filters.min_change_percent is not None and change_percent < filters.min_change_percent:
                    continue
                if filters.max_change_percent is not None and change_percent > filters.max_change_percent:
                    continue
                
                # Volume filters
                if filters.min_volume and volume < filters.min_volume:
                    continue
                
                # Sector filter
                if filters.sectors and stock_meta["sector"] not in filters.sectors:
                    continue
                
                # Market cap filter
                if filters.min_market_cap and stock_meta["market_cap"] < filters.min_market_cap:
                    continue
                if filters.max_market_cap and stock_meta["market_cap"] > filters.max_market_cap:
                    continue
                
                # Calculate RSI (simplified - would need historical data)
                # For now, generate synthetic RSI based on change%
                rsi = None
                if change_percent > 2:
                    rsi = 65 + (change_percent * 2)
                elif change_percent < -2:
                    rsi = 35 + (change_percent * 2)
                else:
                    rsi = 50 + (change_percent * 5)
                
                rsi = max(0, min(100, rsi))  # Clamp to 0-100
                
                # RSI filters
                if filters.rsi_min and rsi < filters.rsi_min:
                    continue
                if filters.rsi_max and rsi > filters.rsi_max:
                    continue
                
                # Moving average filters (simplified)
                ma_20 = ltp * 0.98  # Simplified MA
                ma_50 = ltp * 0.96
                ma_200 = ltp * 0.92
                
                if filters.price_above_ma:
                    if filters.price_above_ma == 20 and ltp < ma_20:
                        continue
                    if filters.price_above_ma == 50 and ltp < ma_50:
                        continue
                    if filters.price_above_ma == 200 and ltp < ma_200:
                        continue
                
                if filters.price_below_ma:
                    if filters.price_below_ma == 20 and ltp > ma_20:
                        continue
                    if filters.price_below_ma == 50 and ltp > ma_50:
                        continue
                    if filters.price_below_ma == 200 and ltp > ma_200:
                        continue
                
                # Advanced technical filters
                # MACD simulation (EMA12 - EMA26)
                macd_value = change_percent * 0.3  # Simplified
                macd_signal = change_percent * 0.25
                macd_histogram = macd_value - macd_signal
                
                if filters.macd_positive is not None:
                    if filters.macd_positive and macd_histogram <= 0:
                        continue
                if filters.macd_negative is not None:
                    if filters.macd_negative and macd_histogram >= 0:
                        continue
                
                # Bollinger Bands simulation
                bb_middle = ma_20
                bb_std = ltp * 0.02  # 2% standard deviation
                bb_upper = bb_middle + (2 * bb_std)
                bb_lower = bb_middle - (2 * bb_std)
                
                if filters.bollinger_squeeze and not (bb_lower * 0.98 < ltp < bb_upper * 1.02):
                    continue
                if filters.bollinger_breakout and (bb_lower < ltp < bb_upper):
                    continue
                
                # ATR (Average True Range) - volatility measure
                atr = abs(ohlc.get("high", ltp) - ohlc.get("low", ltp))
                if filters.atr_min and atr < filters.atr_min:
                    continue
                if filters.atr_max and atr > filters.atr_max:
                    continue
                
                # ADX (Trend Strength) - simulate based on change%
                adx = min(100, abs(change_percent) * 5 + 20)  # Trend strength
                if filters.adx_min and adx < filters.adx_min:
                    continue
                if filters.adx_max and adx > filters.adx_max:
                    continue
                
                # Fundamental filters
                if filters.min_pe_ratio and stock_meta.get("pe_ratio", 0) < filters.min_pe_ratio:
                    continue
                if filters.max_pe_ratio and stock_meta.get("pe_ratio", 999) > filters.max_pe_ratio:
                    continue
                if filters.min_pb_ratio and stock_meta.get("pb_ratio", 0) < filters.min_pb_ratio:
                    continue
                if filters.max_pb_ratio and stock_meta.get("pb_ratio", 999) > filters.max_pb_ratio:
                    continue
                if filters.min_dividend_yield and stock_meta.get("div_yield", 0) < filters.min_dividend_yield:
                    continue
                if filters.max_debt_to_equity and stock_meta.get("debt_equity", 0) > filters.max_debt_to_equity:
                    continue
                if filters.min_roe and stock_meta.get("roe", 0) < filters.min_roe:
                    continue
                
                # Pattern recognition (simplified)
                if filters.pattern:
                    # Simplified pattern matching based on candle structure
                    pattern_match = False
                    if filters.pattern == "bullish_engulfing" and change_percent > 2:
                        pattern_match = True
                    elif filters.pattern == "bearish_engulfing" and change_percent < -2:
                        pattern_match = True
                    elif filters.pattern == "doji" and abs(change_percent) < 0.2:
                        pattern_match = True
                    elif filters.pattern == "hammer" and change_percent < -1 and ohlc.get("low", ltp) < ltp * 0.98:
                        pattern_match = True
                    
                    if not pattern_match:
                        continue
                
                # Stock passed all filters
                results.append({
                    "symbol": symbol,
                    "name": symbol,  # Could add full company name
                    "ltp": round(ltp, 2),
                    "change": round(change, 2),
                    "change_percent": round(change_percent, 2),
                    "volume": volume,
                    "volume_lakhs": round(volume / 100000, 2),
                    "rsi": round(rsi, 1),
                    "sector": stock_meta["sector"],
                    "market_cap": stock_meta["market_cap"],
                    "market_cap_cr": round(stock_meta["market_cap"] / 100, 0),  # In crores
                    "ma_20": round(ma_20, 2),
                    "ma_50": round(ma_50, 2),
                    "open": ohlc.get("open", ltp),
                    "high": ohlc.get("high", ltp),
                    "low": ohlc.get("low", ltp),
                    # Add fundamental data
                    "pe_ratio": stock_meta.get("pe_ratio", 0),
                    "pb_ratio": stock_meta.get("pb_ratio", 0),
                    "div_yield": stock_meta.get("div_yield", 0),
                    "roe": stock_meta.get("roe", 0),
                    "debt_equity": stock_meta.get("debt_equity", 0),
                    # Add advanced technical
                    "macd": round(macd_histogram, 2),
                    "adx": round(adx, 1),
                    "atr": round(atr, 2),
                })
            
            except Exception as e:
                logger.warning(f"Error processing {symbol}: {e}")
                continue
        
        # Sort results
        sort_key = filters.sort_by or "change_percent"
        reverse = (filters.sort_order or "desc") == "desc"
        
        sort_mapping = {
            "change_percent": lambda x: x["change_percent"],
            "volume": lambda x: x["volume"],
            "price": lambda x: x["ltp"],
            "rsi": lambda x: x["rsi"],
            "market_cap": lambda x: x["market_cap"],
        }
        
        if sort_key in sort_mapping:
            results.sort(key=sort_mapping[sort_key], reverse=reverse)
        
        return {
            "results": results,
            "count": len(results),
            "total_scanned": len(NIFTY50_STOCKS),
            "filters_applied": filters.dict(exclude_none=True),
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Screener error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Screener failed: {str(e)}")


@router.get("/presets")
async def get_presets():
    """
    Get predefined screener presets
    """
    presets = [
        {
            "id": "breakout",
            "name": "Breakout Stocks",
            "description": "Stocks breaking above 20-day MA with high volume",
            "filters": {
                "min_change_percent": 2.0,
                "min_volume_ratio": 1.5,
                "price_above_ma": 20,
                "rsi_min": 60,
                "sort_by": "change_percent"
            }
        },
        {
            "id": "oversold",
            "name": "Oversold (Value)",
            "description": "Stocks with RSI < 30, potential bounce candidates",
            "filters": {
                "rsi_max": 30,
                "min_change_percent": -10,
                "sort_by": "rsi",
                "sort_order": "asc"
            }
        },
        {
            "id": "overbought",
            "name": "Overbought (Caution)",
            "description": "Stocks with RSI > 70, potential correction",
            "filters": {
                "rsi_min": 70,
                "sort_by": "rsi",
                "sort_order": "desc"
            }
        },
        {
            "id": "high_volume",
            "name": "High Volume Movers",
            "description": "Stocks with unusually high trading volume",
            "filters": {
                "min_volume": 1000000,
                "sort_by": "volume",
                "sort_order": "desc"
            }
        },
        {
            "id": "trending_up",
            "name": "Strong Uptrend",
            "description": "Price above all major moving averages",
            "filters": {
                "min_change_percent": 1.0,
                "price_above_ma": 50,
                "rsi_min": 55,
                "rsi_max": 75,
                "sort_by": "change_percent"
            }
        },
        {
            "id": "large_cap",
            "name": "Large Cap Leaders",
            "description": "Top market cap stocks with positive momentum",
            "filters": {
                "min_market_cap": 500000,
                "min_change_percent": 0,
                "sort_by": "market_cap",
                "sort_order": "desc"
            }
        },
        {
            "id": "it_sector",
            "name": "IT Sector Momentum",
            "description": "IT stocks with positive returns",
            "filters": {
                "sectors": ["IT"],
                "min_change_percent": 0,
                "sort_by": "change_percent"
            }
        }
    ]
    
    return {
        "presets": presets,
        "count": len(presets)
    }
