"""
Stock News API - newsdata.io integration
Provides real-time news for specific symbols with caching to save API credits
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict
import httpx
import os
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# newsdata.io API configuration
NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY", "")
NEWSDATA_BASE_URL = "https://newsdata.io/api/1/market"  # Using /market endpoint which supports symbol parameter

# In-memory cache for news articles (to save API credits)
# Format: {symbol: {"articles": [...], "timestamp": datetime, "total": int}}
NEWS_CACHE: Dict[str, dict] = {}
CACHE_DURATION_MINUTES = 30  # Cache news for 30 minutes to save credits

# Company name mapping for better news search
COMPANY_NAMES = {
    "RELIANCE": "Reliance Industries",
    "TCS": "Tata Consultancy Services",
    "INFY": "Infosys",
    "HDFCBANK": "HDFC Bank",
    "ICICIBANK": "ICICI Bank",
    "SBIN": "State Bank of India",
    "BHARTIARTL": "Bharti Airtel",
    "KOTAKBANK": "Kotak Mahindra Bank",
    "BAJFINANCE": "Bajaj Finance",
    "LT": "Larsen & Toubro",
    "AXISBANK": "Axis Bank",
    "MARUTI": "Maruti Suzuki",
    "TITAN": "Titan Company",
    "SUNPHARMA": "Sun Pharma",
    "WIPRO": "Wipro",
    "HCLTECH": "HCL Technologies",
    "TECHM": "Tech Mahindra",
    "ULTRACEMCO": "UltraTech Cement",
    "NESTLEIND": "Nestle India",
    "ASIANPAINT": "Asian Paints",
    "INDUSINDBK": "IndusInd Bank",
    "TATAMOTORS": "Tata Motors",
    "TATASTEEL": "Tata Steel",
    "HINDALCO": "Hindalco",
    "ADANIGREEN": "Adani Green Energy",
    "ADANIPORTS": "Adani Ports",
    "COALINDIA": "Coal India",
    "NTPC": "NTPC",
    "ONGC": "ONGC",
    "POWERGRID": "Power Grid",
    "ITC": "ITC Limited",
    "HINDUNILVR": "Hindustan Unilever",
    "BRITANNIA": "Britannia Industries",
    "DRREDDY": "Dr Reddy's Laboratories",
    "APOLLOHOSP": "Apollo Hospitals",
    "DIVISLAB": "Divi's Laboratories",
    "CIPLA": "Cipla",
    "BAJAJFINSV": "Bajaj Finserv",
    "BAJAJ-AUTO": "Bajaj Auto",
    "HEROMOTOCO": "Hero MotoCorp",
    "EICHERMOT": "Eicher Motors",
    "M&M": "Mahindra & Mahindra",
    "GRASIM": "Grasim Industries",
    "JSWSTEEL": "JSW Steel",
    "TATACONSUM": "Tata Consumer Products",
    "SHREECEM": "Shree Cement",
    "HDFCLIFE": "HDFC Life",
    "SBILIFE": "SBI Life",
    "BAJAJHLDNG": "Bajaj Holdings",
    "ICICIGI": "ICICI Lombard",
    "PFC": "Power Finance Corporation",
    "RECLTD": "REC Limited",
    "MUTHOOTFIN": "Muthoot Finance",
    "CHOLAFIN": "Cholamandalam Investment",
    "LTIM": "LTIMindtree",
    "COFORGE": "Coforge",
    "PERSISTENT": "Persistent Systems",
    "MPHASIS": "Mphasis",
    "UPL": "UPL Limited",
    "BPCL": "Bharat Petroleum",
}


def is_cache_valid(symbol: str) -> bool:
    """Check if cached news for symbol is still valid"""
    if symbol not in NEWS_CACHE:
        return False
    
    cache_entry = NEWS_CACHE[symbol]
    cache_age = datetime.now() - cache_entry["timestamp"]
    is_valid = cache_age < timedelta(minutes=CACHE_DURATION_MINUTES)
    
    if is_valid:
        logger.info(f"💾 Cache HIT for {symbol} (age: {cache_age.seconds//60} minutes)")
    else:
        logger.info(f"⏰ Cache EXPIRED for {symbol} (age: {cache_age.seconds//60} minutes)")
    
    return is_valid


async def fetch_newsdata_io(symbol: str, limit: int = 10) -> List[dict]:
    """
    Fetch news from newsdata.io API with caching
    Cache duration: {CACHE_DURATION_MINUTES} minutes to save API credits (200 credits/day, 10 per article)
    """
    logger.info(f"🔍 fetch_newsdata_io called for {symbol}, API_KEY present: {bool(NEWSDATA_API_KEY)}")
    
    # Check cache first to save API credits
    if is_cache_valid(symbol):
        cached_data = NEWS_CACHE[symbol]
        logger.info(f"✅ Returning {len(cached_data['articles'])} cached articles for {symbol}")
        return cached_data["articles"]
    logger.debug(f"API Key value: {NEWSDATA_API_KEY[:20]}..." if NEWSDATA_API_KEY else "API Key: NOT SET")
    
    if not NEWSDATA_API_KEY:
        logger.warning("❌ NEWSDATA_API_KEY not configured, returning empty news list")
        return []
    
    logger.info(f"🔎 Fetching latest news for: {symbol}")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Use /news endpoint with symbol parameter (specifically designed for stock tickers)
            params = {
                "apikey": NEWSDATA_API_KEY,
                "symbol": symbol,  # Use symbol parameter for stock-specific news
                "country": "in",  # India
                "language": "en",

            }
            
            logger.info(f"📡 Calling newsdata.io /market API with symbol: {symbol}")
            response = await client.get(NEWSDATA_BASE_URL, params=params)
            logger.info(f"📊 API Response Status: {response.status_code}")
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"📥 API Response data keys: {data.keys() if isinstance(data, dict) else 'N/A'}")
            logger.info(f"📥 Response status: {data.get('status')}")
            logger.info(f"📥 Full API Response (first 500 chars): {str(data)[:500]}")
            
            if data.get("status") != "success":
                logger.error(f"❌ newsdata.io API error: {data.get('message', 'Unknown error')}")
                return []
            
            articles = []
            all_results = data.get("results", [])
            logger.info(f"📊 Total results from API: {len(all_results)}")
            
            for idx, result in enumerate(all_results):
                # Handle None values safely
                title = (result.get("title") or "").lower()
                desc = (result.get("description") or "").lower()
                content = title + " " + desc
                
                # Skip if completely empty
                if not content.strip():
                    logger.debug(f"⏭️ Skipping empty article #{idx}")
                    continue
                
                # Since we're using symbol parameter, most results should be relevant
                # But do basic filtering to remove completely unrelated articles
                has_company = symbol.lower() in content
                has_stock_keywords = any(word in content for word in ["stock", "share", "price", "market", "trading", "dividend", "listing"])
                
                # Accept if mentions company/symbol OR has stock-related keywords
                if not (has_company or has_stock_keywords):
                    logger.debug(f"⏭️ Filtering out non-stock article: {title[:50]}")
                    continue
                
                # Simple sentiment analysis based on keywords
                sentiment = "neutral"
                
                positive_keywords = ["profit", "growth", "surge", "gain", "up", "rally", "bullish", "earnings beat", "success", "rise", "outperform"]
                negative_keywords = ["loss", "decline", "fall", "down", "crash", "bearish", "miss", "cut", "weak", "drop", "underperform"]
                
                positive_score = sum(1 for keyword in positive_keywords if keyword in content)
                negative_score = sum(1 for keyword in negative_keywords if keyword in content)
                
                if positive_score > negative_score:
                    sentiment = "positive"
                elif negative_score > positive_score:
                    sentiment = "negative"
                
                articles.append({
                    "title": result.get("title", ""),
                    "description": result.get("description", ""),
                    "source": result.get("source_id", "Unknown"),
                    "url": result.get("link", ""),
                    "publishedAt": result.get("pubDate", ""),
                    "sentiment": sentiment,
                    "imageUrl": result.get("image_url"),
                })
            
            logger.info(f"✅ Found {len(articles)} relevant articles for {symbol} (filtered from {len(all_results)} total)")
            
            # Cache the results to save API credits
            NEWS_CACHE[symbol] = {
                "articles": articles,
                "timestamp": datetime.now(),
                "total": len(articles)
            }
            logger.info(f"💾 Cached {len(articles)} articles for {symbol} (valid for {CACHE_DURATION_MINUTES} minutes)")
            
            return articles
            
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ newsdata.io HTTP error: {e}")
        logger.error(f"Response body: {e.response.text}")
        return []
    except Exception as e:
        logger.error(f"❌ Error fetching news from newsdata.io: {e}", exc_info=True)
        return []


@router.get("/stock-news/{symbol}")
async def get_stock_news(
    symbol: str,
    limit: int = Query(10, ge=1, le=50, description="Number of articles to fetch")
):
    """
    Get news articles for a specific stock symbol from newsdata.io
    
    Returns:
        - articles: List of news articles with title, description, source, url, sentiment
        - total: Total number of articles
        - symbol: Symbol queried
        - company: Full company name
    """
    try:
        symbol = symbol.upper()
        company_name = COMPANY_NAMES.get(symbol, symbol)
        
        logger.info(f"📰 Fetching news for {symbol} ({company_name}), API_KEY configured: {bool(NEWSDATA_API_KEY)}")
        
        # Check if API key is configured
        if not NEWSDATA_API_KEY:
            logger.warning(f"⚠️ NEWSDATA_API_KEY not configured! Cannot fetch news")
            return {
                "symbol": symbol,
                "company": company_name,
                "articles": [],
                "total": 0,
                "data_source": "unavailable",
                "error": "API key not configured",
                "timestamp": datetime.now().isoformat()
            }
        
        # Check if data will come from cache BEFORE fetching
        was_cached_before_fetch = is_cache_valid(symbol)
        
        articles = await fetch_newsdata_io(symbol, limit)
        
        logger.info(f"✅ News endpoint returning {len(articles)} articles for {symbol}")
        
        # Determine cache age if it was cached
        cache_age_minutes = None
        if was_cached_before_fetch and symbol in NEWS_CACHE:
            cache_age = datetime.now() - NEWS_CACHE[symbol]["timestamp"]
            cache_age_minutes = cache_age.seconds // 60
        
        return {
            "symbol": symbol,
            "company": company_name,
            "articles": articles,
            "total": len(articles),
            "data_source": "newsdata.io",
            "cached": was_cached_before_fetch,
            "cache_age_minutes": cache_age_minutes,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error in get_stock_news: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch stock news: {str(e)}")


@router.get("/stock-news-cache/status")
async def get_cache_status():
    """
    Get current cache status and statistics
    Useful for monitoring API credit usage
    """
    cache_info = []
    for symbol, data in NEWS_CACHE.items():
        cache_age = datetime.now() - data["timestamp"]
        cache_info.append({
            "symbol": symbol,
            "articles_count": data["total"],
            "cached_at": data["timestamp"].isoformat(),
            "age_minutes": cache_age.seconds // 60,
            "is_valid": cache_age < timedelta(minutes=CACHE_DURATION_MINUTES)
        })
    
    return {
        "cache_duration_minutes": CACHE_DURATION_MINUTES,
        "cached_symbols": len(NEWS_CACHE),
        "cache_entries": cache_info,
        "credits_saved_estimate": sum(d["total"] for d in NEWS_CACHE.values()) * 10,  # 10 credits per article
        "timestamp": datetime.now().isoformat()
    }


@router.post("/stock-news-cache/clear")
async def clear_cache(symbol: Optional[str] = None):
    """
    Clear news cache
    - If symbol provided: Clear cache for that symbol only
    - If no symbol: Clear entire cache
    """
    if symbol:
        symbol = symbol.upper()
        if symbol in NEWS_CACHE:
            del NEWS_CACHE[symbol]
            logger.info(f"🗑️ Cleared cache for {symbol}")
            return {"message": f"Cache cleared for {symbol}", "status": "success"}
        else:
            return {"message": f"No cache found for {symbol}", "status": "not_found"}
    else:
        cleared_count = len(NEWS_CACHE)
        NEWS_CACHE.clear()
        logger.info(f"🗑️ Cleared entire news cache ({cleared_count} symbols)")
        return {"message": f"Cleared cache for {cleared_count} symbols", "status": "success"}

