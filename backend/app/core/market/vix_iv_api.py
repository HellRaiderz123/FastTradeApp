"""
vix_iv_api.py
-------------
Fetches real VIX and IV Rank data from APIs and database.

Sources:
1. India VIX: NSE API, Zerodha, Yahoo Finance
2. IV Rank: Computed from 52-week VIX range (stored in database)
3. Fallback: Default values if APIs unavailable
"""

import requests
import logging
from typing import Dict, Tuple, Optional
import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ========================================================================
# INDIA VIX (NSE)
# ========================================================================

def get_india_vix() -> Optional[float]:
    """
    Fetch India VIX from NSE website.
    
    Returns:
        India VIX value (float) or None if unavailable
        
    Note: NSE website doesn't have a direct API, but we can:
    1. Scrape from NSE website
    2. Use public data feeds
    3. Fall back to cached value
    """
    try:
        # Approach 1: Try NSE public endpoint (if available)
        url = "https://www.nseindia.com/live_market/movers/niftyVolatility.jsp"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            # Parse the response (NSE returns HTML, need to extract VIX value)
            # This is a simplified approach - actual parsing would depend on HTML structure
            import re
            vix_match = re.search(r'India VIX[^>]*>([0-9.]+)<', response.text, re.IGNORECASE)
            if vix_match:
                vix_value = float(vix_match.group(1))
                logger.info(f"✅ Fetched India VIX from NSE: {vix_value}")
                return vix_value
        
        logger.warning("Could not parse VIX from NSE website")
        
    except requests.exceptions.RequestException as e:
        logger.warning(f"⚠️  NSE VIX API error: {e}")
    except Exception as e:
        logger.warning(f"⚠️  Error fetching India VIX: {e}")
    
    return None


def get_india_vix_from_nse_api() -> Optional[float]:
    """
    Alternative: Fetch from NSE API (requires proper endpoint)
    Many free APIs provide this data.
    """
    try:
        # Option 1: Try a free public API (example)
        # This is a placeholder - you'd need to find a real working endpoint
        # Some options:
        # - Moneycontrol API (unofficial)
        # - Zerodha Instruments (check if VIX is included)
        # - Other financial data providers
        
        url = "https://query1.finance.yahoo.com/v7/finance/quote"
        params = {"symbols": "^NSEINDEXVIX", "fields": "regularMarketPrice"}
        
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if "quoteResponse" in data and data["quoteResponse"]["result"]:
                vix_price = data["quoteResponse"]["result"][0].get("regularMarketPrice")
                if vix_price:
                    logger.info(f"✅ Fetched India VIX from Yahoo Finance: {vix_price}")
                    return float(vix_price)
    
    except Exception as e:
        logger.warning(f"⚠️  Yahoo Finance VIX API error: {e}")
    
    return None


def get_india_vix_from_zerodha() -> Optional[float]:
    """
    Fetch India VIX from Zerodha if available in instruments.
    NSE:NIFTYIT VIX token might be available.
    """
    try:
        from app.core.broker.zerodha.client import get_kite_client
        from app.core.broker.zerodha.instruments import get_index_token
        
        kite = get_kite_client()
        
        # Try to get NIFTY VIX (index token might be available)
        try:
            data = kite.ltp(["NSE:INDIA VIX"])
            vix = data["NSE:INDIA VIX"]["last_price"]
            logger.info(f"✅ INDIA VIX fetched: {vix}")
            return float(vix)

        except Exception as e:
            logger.warning(f"⚠️ Zerodha VIX fetch failed: {e}")
            return None
        
        # Try alternate symbol
        try:
            # NIFTY VIX might be under different token
            response = kite.ltp(["NSE:NIFTYIT"])
            logger.warning("Could not fetch NIFTY VIX from Zerodha")
        except:
            pass
    
    except Exception as e:
        logger.warning(f"⚠️  Zerodha VIX fetch error: {e}")
    
    return None


# ========================================================================
# IV RANK (Implied Volatility Percentile)
# ========================================================================

def compute_iv_rank_from_option_chain(chain_df: pd.DataFrame) -> Optional[float]:
    """
    Compute IV Rank from option chain data.
    
    IV Rank = (Current IV - 52-Week Low IV) / (52-Week High IV - 52-Week Low IV) * 100
    
    For now, we'll use implied volatility from ATM options.
    In production, would need 52-week IV history.
    """
    try:
        if chain_df.empty:
            return None
        
        # Get ATM Call option (proxy for current IV)
        # In real scenario, would compute IV from bid-ask, historical data, etc.
        atm_options = chain_df[
            chain_df["instrument_type"].isin(["CE", "PE"])
        ]
        
        if len(atm_options) == 0:
            return None
        
        # Placeholder: Estimate IV rank from current prices
        # This is simplified - real IV rank needs complex calculations
        # For now, estimate from option premiums as proxy
        
        call_prices = atm_options[atm_options["instrument_type"] == "CE"]["ltp"].values
        put_prices = atm_options[atm_options["instrument_type"] == "PE"]["ltp"].values
        
        if len(call_prices) == 0 or len(put_prices) == 0:
            return None
        
        # Simple heuristic: Estimate IV rank from option premium levels
        avg_call = call_prices.mean()
        avg_put = put_prices.mean()
        
        # Very rough estimate (would need proper Black-Scholes in production)
        estimated_iv_rank = min(100, (avg_call + avg_put) / 2)
        
        logger.info(f"✅ Computed estimated IV Rank: {estimated_iv_rank:.2f}")
        return estimated_iv_rank
        
    except Exception as e:
        logger.warning(f"⚠️  Error computing IV rank: {e}")
        return None


def get_iv_rank_from_api() -> Optional[float]:
    """
    Fetch IV Rank from database (calculated from 52-week VIX range).
    
    IV Rank = (Current VIX - 52w Low) / (52w High - 52w Low) * 100
    
    This requires:
    1. Historic VIX data stored in database
    2. Daily updates via zerodha_historic_fetcher
    """
    try:
        from app.db.session import SessionLocal
        from app.core.market.iv_rank_calculator import get_latest_iv_rank
        from app.core.market.zerodha_historic_fetcher import fetch_and_store_daily_vix
        
        db = SessionLocal()
        try:
            # Update today's VIX if not already done
            fetch_and_store_daily_vix(db)
            
            # Get latest calculated IV Rank
            iv_rank = get_latest_iv_rank(db)
            
            if iv_rank is not None:
                logger.info(f"✅ IV Rank fetched from database: {iv_rank:.2f}%")
                return iv_rank
            else:
                logger.warning("⚠️  IV Rank not available in database yet")
                return None
                
        finally:
            db.close()
            
    except Exception as e:
        logger.warning(f"⚠️  IV Rank API error: {e}")
        return None


# ========================================================================
# MAIN FETCHER FUNCTION
# ========================================================================

def get_vix_iv_data() -> Dict[str, Optional[float]]:
    """
    Fetch VIX and IV Rank data from all available sources.
    
    Returns:
        {
            "india_vix": float or None,
            "iv_rank": float or None,
            "vix_source": str (where it came from),
            "iv_source": str
        }
    """
    
    result = {
        "india_vix": None,
        "iv_rank": None,
        "vix_source": "fallback",
        "iv_source": "fallback"
    }
    
    # Try to fetch India VIX from multiple sources
    india_vix = None
    
    # Try 1: Zerodha
    india_vix = get_india_vix_from_zerodha()
    if india_vix is not None:
        result["india_vix"] = india_vix
        result["vix_source"] = "zerodha"
    
    # Try 2: Yahoo Finance
    if india_vix is None:
        india_vix = get_india_vix_from_nse_api()
        if india_vix is not None:
            result["india_vix"] = india_vix
            result["vix_source"] = "yahoo_finance"
    
    # Try 3: NSE website scrape
    if india_vix is None:
        india_vix = get_india_vix()
        if india_vix is not None:
            result["india_vix"] = india_vix
            result["vix_source"] = "nse_website"
    
    # Fallback to default
    if india_vix is None:
        result["india_vix"] = 10.1  # Default fallback
        result["vix_source"] = "fallback (hardcoded)"
        logger.warning(f"⚠️  Using fallback India VIX: {result['india_vix']}")
    
    # Try to fetch IV Rank
    iv_rank = get_iv_rank_from_api()
    if iv_rank is not None:
        result["iv_rank"] = iv_rank
        result["iv_source"] = "external_api"
    
    # Fallback to default
    if iv_rank is None:
        result["iv_rank"] = 7.26  # Default fallback
        result["iv_source"] = "fallback (hardcoded)"
        logger.warning(f"⚠️  Using fallback IV Rank: {result['iv_rank']}")
    
    logger.info(f"✅ VIX/IV Data: VIX={result['india_vix']} (from {result['vix_source']}), "
                f"IV_Rank={result['iv_rank']} (from {result['iv_source']})")
    
    return result


def determine_iv_regime(india_vix: float, iv_rank: float) -> str:
    """
    Determine IV regime based on VIX and IV Rank values.
    
    Returns: "LOW", "NORMAL", or "HIGH"
    """
    
    # IV Rank tells us historical percentile
    # India VIX tells us absolute level
    
    if iv_rank >= 75 or india_vix >= 30:
        return "HIGH"
    elif iv_rank >= 50 and india_vix >= 20:
        return "NORMAL_HIGH"
    elif iv_rank >= 50:
        return "NORMAL"
    elif iv_rank >= 25 and india_vix >= 15:
        return "NORMAL_LOW"
    else:
        return "LOW"


# ========================================================================
# CACHE (to avoid repeated API calls)
# ========================================================================

_vix_iv_cache = {
    "data": None,
    "timestamp": None,
    "ttl_seconds": 60  # Cache for 1 minute
}


def get_vix_iv_data_cached() -> Dict[str, Optional[float]]:
    """
    Get VIX/IV data with caching to reduce API calls.
    """
    import time
    
    current_time = time.time()
    
    # Check if cache is valid
    if (
        _vix_iv_cache["data"] is not None and
        _vix_iv_cache["timestamp"] is not None and
        (current_time - _vix_iv_cache["timestamp"]) < _vix_iv_cache["ttl_seconds"]
    ):
        logger.debug("✅ Using cached VIX/IV data")
        return _vix_iv_cache["data"]
    
    # Fetch fresh data
    data = get_vix_iv_data()
    _vix_iv_cache["data"] = data
    _vix_iv_cache["timestamp"] = current_time
    
    return data
