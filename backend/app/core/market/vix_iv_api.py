"""
vix_iv_api.py
-------------
Fetches India VIX and VIX Rank (NOT option IV rank).

Design principles:
1. India VIX is the PRIMARY driver of IV regime
2. VIX Rank (historical percentile of VIX) is SECONDARY confirmation only
3. ATM option IV is NOT used here (future enhancement)

Regime output: LOW | NORMAL | HIGH
"""

import requests
import logging
from typing import Dict, Optional
from datetime import datetime
import time

logger = logging.getLogger(__name__)

# ========================================================================
# INDIA VIX FETCHERS
# ========================================================================

def get_india_vix_from_zerodha() -> Optional[float]:
    """
    Fetch India VIX from Zerodha LTP if available.
    """
    try:
        from app.core.broker.zerodha.client import get_kite_client

        kite = get_kite_client()
        data = kite.ltp(["NSE:INDIA VIX"])
        vix = data["NSE:INDIA VIX"]["last_price"]

        logger.info(f"✅ India VIX fetched from Zerodha: {vix}")
        return float(vix)

    except Exception as e:
        logger.warning(f"⚠️ Zerodha VIX fetch failed: {e}")
        return None


def get_india_vix_from_yahoo() -> Optional[float]:
    """
    Fetch India VIX from Yahoo Finance.
    """
    try:
        url = "https://query1.finance.yahoo.com/v7/finance/quote"
        params = {"symbols": "^NSEINDEXVIX"}

        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            result = data.get("quoteResponse", {}).get("result", [])
            if result:
                vix = result[0].get("regularMarketPrice")
                if vix is not None:
                    logger.info(f"✅ India VIX fetched from Yahoo: {vix}")
                    return float(vix)

    except Exception as e:
        logger.warning(f"⚠️ Yahoo VIX fetch error: {e}")

    return None


def get_india_vix_from_nse_scrape() -> Optional[float]:
    """
    Fallback: scrape India VIX from NSE website (best effort).
    """
    try:
        url = "https://www.nseindia.com/live_market/movers/niftyVolatility.jsp"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
        }

        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            import re
            match = re.search(r"India VIX[^>]*>([0-9.]+)<", response.text)
            if match:
                vix = float(match.group(1))
                logger.info(f"✅ India VIX scraped from NSE: {vix}")
                return vix

    except Exception as e:
        logger.warning(f"⚠️ NSE scrape error: {e}")

    return None


# ========================================================================
# VIX RANK (HISTORICAL CONTEXT ONLY)
# ========================================================================

def get_vix_rank_from_db() -> Optional[float]:
    """
    Fetch latest VIX Rank from database.
    This is VIX percentile over last 52 weeks.
    """
    try:
        from app.db.session import SessionLocal
        from app.core.market.iv_rank_calculator import get_latest_iv_rank
        from app.core.market.zerodha_historic_fetcher import fetch_and_store_daily_vix

        db = SessionLocal()
        try:
            # Ensure today's VIX is stored
            fetch_and_store_daily_vix(db)

            vix_rank = get_latest_iv_rank(db)
            if vix_rank is not None:
                logger.info(f"✅ VIX Rank fetched from DB: {vix_rank:.2f}%")
                return float(vix_rank)

        finally:
            db.close()

    except Exception as e:
        logger.warning(f"⚠️ VIX Rank fetch error: {e}")

    return None


# ========================================================================
# MAIN FETCHER
# ========================================================================

def get_vix_iv_data() -> Dict[str, Optional[float]]:
    """
    Fetch India VIX and VIX Rank with fallbacks.

    Returns:
    {
        "india_vix": float,
        "vix_rank": float | None,
        "vix_source": str,
        "vix_rank_source": str
    }
    """

    result = {
        "india_vix": None,
        "vix_rank": None,
        "vix_source": "fallback",
        "vix_rank_source": "fallback",
    }

    # ---- India VIX ----
    vix = get_india_vix_from_zerodha()
    if vix is not None:
        result["india_vix"] = vix
        result["vix_source"] = "zerodha"
    else:
        vix = get_india_vix_from_yahoo()
        if vix is not None:
            result["india_vix"] = vix
            result["vix_source"] = "yahoo"
        else:
            vix = get_india_vix_from_nse_scrape()
            if vix is not None:
                result["india_vix"] = vix
                result["vix_source"] = "nse_scrape"

    # Hard fallback (safe default)
    if result["india_vix"] is None:
        result["india_vix"] = 18.0
        result["vix_source"] = "hardcoded"
        logger.warning("⚠️ Using fallback India VIX = 18.0")

    # ---- VIX Rank ----
    vix_rank = get_vix_rank_from_db()
    if vix_rank is not None:
        result["vix_rank"] = vix_rank
        result["vix_rank_source"] = "database"

    logger.info(
        f"📊 VIX Data | India VIX={result['india_vix']} ({result['vix_source']}), "
        f"VIX Rank={result['vix_rank']} ({result['vix_rank_source']})"
    )

    return result


# ========================================================================
# CLEAN IV REGIME LOGIC (CANONICAL)
# ========================================================================

def determine_iv_regime(
    *,
    india_vix: float,
    vix_rank: Optional[float] = None,
) -> str:
    """
    Determine IV regime.

    RULES:
    - India VIX is primary
    - VIX Rank can only soften extremes
    """

    # Primary regime from India VIX
    if india_vix >= 20:
        base = "HIGH"
    elif india_vix >= 14:
        base = "NORMAL"
    else:
        base = "LOW"

    # Secondary adjustment using VIX Rank
    if vix_rank is not None:
        if base == "LOW" and vix_rank >= 80:
            return "NORMAL"
        if base == "HIGH" and vix_rank <= 20:
            return "NORMAL"

    return base


# ========================================================================
# CACHE
# ========================================================================

_vix_cache = {
    "data": None,
    "timestamp": None,
    "ttl": 60,  # seconds
}


def get_vix_iv_data_cached() -> Dict[str, Optional[float]]:
    """
    Cached access to VIX/VIX Rank data.
    """
    now = time.time()

    if (
        _vix_cache["data"] is not None
        and _vix_cache["timestamp"] is not None
        and (now - _vix_cache["timestamp"]) < _vix_cache["ttl"]
    ):
        return _vix_cache["data"]

    data = get_vix_iv_data()
    _vix_cache["data"] = data
    _vix_cache["timestamp"] = now
    return data
