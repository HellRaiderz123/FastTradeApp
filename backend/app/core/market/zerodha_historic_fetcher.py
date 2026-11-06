"""
zerodha_historic_fetcher.py
---------------------------
Fetch historic VIX data from Zerodha and store in database.
"""

import logging
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.core.market.iv_rank_calculator import update_daily_iv_rank

logger = logging.getLogger(__name__)


def fetch_vix_from_zerodha_live() -> Optional[float]:
    """
    Fetch current India VIX. Tries Zerodha token 264969 first, then NSE scrape.
    """
    # Try Zerodha instrument token 264969 (INDIA VIX)
    try:
        from app.core.broker.zerodha.client import get_kite_client
        kite = get_kite_client()
        data = kite.ltp([264969])
        entry = data.get(264969) or data.get("264969")
        if entry:
            vix = float(entry["last_price"])
            if vix > 0:
                logger.info("Fetched INDIA VIX from Zerodha token 264969: %s", vix)
                return vix
    except Exception as e:
        logger.warning("Zerodha VIX token fetch failed: %s", e)

    # Fallback: NSE allIndices scrape
    try:
        from app.core.market.vix_iv_api import get_india_vix_from_nse_scrape
        vix = get_india_vix_from_nse_scrape()
        if vix:
            logger.info("Fetched INDIA VIX from NSE scrape: %s", vix)
            return vix
    except Exception as e:
        logger.warning("NSE VIX scrape fallback failed: %s", e)

    return None


def fetch_vix_historic_from_zerodha(
    db: Session,
    days_back: int = 365,
    force_refresh: bool = False
) -> dict:
    """
    Fetch historic India VIX from NSE chart-databyindex (reliable, no broker token needed).
    Falls back to Zerodha historical API with correct token 264969.
    """
    result = {
        'success': False,
        'records_fetched': 0,
        'records_stored': 0,
        'date_range': None,
        'error': None
    }

    from datetime import date as _date
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days_back)

    # Primary: NSE chart-databyindex returns full VIX series
    try:
        import requests
        NSE_BASE = "https://www.nseindia.com"
        MAC_UA = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        headers = {
            "User-Agent": MAC_UA,
            "Accept": "application/json, */*",
            "Referer": f"{NSE_BASE}/market-data-pre-open/",
        }
        r = requests.get(
            f"{NSE_BASE}/api/chart-databyindex",
            headers=headers,
            params={"index": "INDIAVIX"},
            timeout=10,
        )
        if r.status_code == 200:
            gd = r.json().get("grapthData") or r.json().get("graphData") or []
            for point in gd:
                if not isinstance(point, list) or len(point) < 2:
                    continue
                try:
                    ts_ms, vix_val = point[0], float(point[1])
                    trade_date = _date.fromtimestamp(ts_ms / 1000)
                    if trade_date < start_date:
                        continue
                    update_daily_iv_rank(db, vix_val, trade_date)
                    result['records_stored'] += 1
                except Exception:
                    continue
            result['records_fetched'] = len(gd)
            result['date_range'] = f"{start_date} to {end_date}"
            result['success'] = result['records_stored'] > 0
            if result['success']:
                logger.info("Stored %d VIX records from NSE chart API", result['records_stored'])
                return result
    except Exception as e:
        logger.warning("NSE VIX history fetch failed: %s", e)

    # Fallback: Zerodha historical with correct token 264969
    try:
        from app.core.broker.zerodha.client import get_kite_client
        kite = get_kite_client()
        candles = kite.historical_data(
            instrument_token=264969,
            from_date=start_date,
            to_date=end_date,
            interval="day",
        )
        for candle in candles:
            try:
                trade_date = candle['date'].date() if isinstance(candle['date'], datetime) else candle['date']
                update_daily_iv_rank(db, candle['close'], trade_date)
                result['records_stored'] += 1
            except Exception:
                continue
        result['records_fetched'] = len(candles)
        result['date_range'] = f"{start_date} to {end_date}"
        result['success'] = result['records_stored'] > 0
        if result['success']:
            logger.info("Stored %d VIX records from Zerodha token 264969", result['records_stored'])
    except Exception as e:
        logger.warning("Zerodha VIX historical fetch failed: %s", e)
        result['error'] = str(e)

    return result


def fetch_and_store_daily_vix(db: Session) -> bool:
    """
    Fetch current VIX from Zerodha and update daily record.
    
    Call this daily to keep IV Rank calculations up-to-date.
    
    Args:
        db: Database session
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get current VIX
        current_vix = fetch_vix_from_zerodha_live()
        
        if current_vix is None:
            logger.warning("Could not fetch current VIX")
            return False
        
        # Update database with today's VIX and calculated IV Rank
        iv_rank = update_daily_iv_rank(db, current_vix)
        
        if iv_rank is not None:
            logger.info(f"✅ Stored daily VIX={current_vix}, IV_Rank={iv_rank:.2f}%")
            return True
        else:
            logger.warning("Could not calculate IV Rank")
            return False
            
    except Exception as e:
        logger.error(f"Error in daily VIX fetch/store: {e}")
        return False


def initialize_vix_historic_data(db: Session, initial_days: int = 365) -> bool:
    """
    Initialize historic VIX data on first run.
    
    This populates the database with historical VIX data so IV Rank
    calculations work immediately.
    
    Args:
        db: Database session
        initial_days: How many days of history to load
        
    Returns:
        True if successful
    """
    try:
        from app.db.models import VixHistoric
        
        # Check if data already exists
        existing = db.query(VixHistoric).count()
        if existing > 0:
            logger.info(f"VIX historic data already exists ({existing} records)")
            return True
        
        logger.info(f"Initializing VIX historic data (last {initial_days} days)...")
        
        # Try to fetch from Zerodha
        result = fetch_vix_historic_from_zerodha(db, days_back=initial_days)
        
        if result['success']:
            logger.info(f"✅ Initialized with {result['records_stored']} VIX records")
            return True
        else:
            logger.warning(f"Could not initialize from Zerodha: {result.get('error', 'Unknown error')}")
            
            # Could implement fallback: seed with estimated data
            logger.info("Consider manually seeding VIX data from external source")
            return False
            
    except Exception as e:
        logger.error(f"Error initializing VIX data: {e}")
        return False
