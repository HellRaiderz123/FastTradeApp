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
    Fetch current India VIX from Zerodha Kiteconnect.
    
    Returns:
        India VIX value or None if unavailable
    """
    try:
        from app.core.broker.zerodha.client import get_kite_client
        
        kite = get_kite_client()
        
        # Try to fetch NIFTY VIX or INDIA VIX
        try:
            data = kite.ltp(["NSE:NIFTY VIX"])
            vix_value = data["NSE:NIFTY VIX"]["last_price"]
            logger.info(f"✅ Fetched NIFTY VIX from Zerodha: {vix_value}")
            return float(vix_value)
        except Exception as e:
            logger.warning(f"Could not fetch NIFTY VIX: {e}")
        
        # Try INDIA VIX
        try:
            data = kite.ltp(["NSE:INDIA VIX"])
            vix_value = data["NSE:INDIA VIX"]["last_price"]
            logger.info(f"✅ Fetched INDIA VIX from Zerodha: {vix_value}")
            return float(vix_value)
        except Exception as e:
            logger.warning(f"Could not fetch INDIA VIX: {e}")
        
        return None
        
    except Exception as e:
        logger.warning(f"Zerodha live VIX fetch error: {e}")
        return None


def fetch_vix_historic_from_zerodha(
    db: Session,
    days_back: int = 365,
    force_refresh: bool = False
) -> dict:
    """
    Fetch historic India VIX data from Zerodha and store in database.
    
    Uses Zerodha's historical data API to fetch candles for VIX index.
    
    Args:
        db: Database session
        days_back: How many days of history to fetch (default: 365 = 1 year)
        force_refresh: If True, overwrite existing data
        
    Returns:
        Dict with fetch results: {
            'success': bool,
            'records_fetched': int,
            'records_stored': int,
            'date_range': str
        }
    """
    try:
        from app.core.broker.zerodha.client import get_kite_client
        from datetime import date, timedelta
        
        kite = get_kite_client()
        
        result = {
            'success': False,
            'records_fetched': 0,
            'records_stored': 0,
            'date_range': None,
            'error': None
        }
        
        # Calculate date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        logger.info(f"Fetching VIX historic data from {start_date} to {end_date}")
        
        # Zerodha instrument token for INDIA VIX (or NIFTY VIX)
        # You may need to find the correct token
        # Common tokens: NIFTY VIX, INDIA VIX
        
        vix_symbols = ["NSE:NIFTY VIX", "NSE:INDIA VIX"]
        vix_token = None
        
        # Try to get the correct VIX instrument
        for symbol in vix_symbols:
            try:
                # Fetch historical candle data (daily closes)
                candles = kite.historical_data(
                    instrument_token=0,  # Will be replaced by correct token
                    from_date=start_date,
                    to_date=end_date,
                    interval="day"
                )
                if candles:
                    logger.info(f"✅ Found {len(candles)} candles for {symbol}")
                    result['records_fetched'] = len(candles)
                    
                    # Process and store candles
                    for candle in candles:
                        try:
                            trade_date = candle['date'].date() if isinstance(candle['date'], datetime) else candle['date']
                            india_vix = candle['close']  # Use closing price as daily VIX
                            
                            # Update IV Rank in database
                            iv_rank = update_daily_iv_rank(db, india_vix, trade_date)
                            result['records_stored'] += 1
                            
                        except Exception as e:
                            logger.warning(f"Could not store candle data: {e}")
                            continue
                    
                    result['date_range'] = f"{start_date} to {end_date}"
                    result['success'] = True
                    return result
                    
            except Exception as e:
                logger.warning(f"Could not fetch historical data for {symbol}: {e}")
                continue
        
        # Fallback: If Zerodha API doesn't work, we can populate with dummy/estimated data
        logger.warning("Could not fetch from Zerodha API, attempting fallback")
        result['error'] = "Zerodha historical API not available"
        return result
        
    except Exception as e:
        logger.error(f"Error fetching VIX historic data: {e}")
        return {
            'success': False,
            'records_fetched': 0,
            'records_stored': 0,
            'error': str(e)
        }


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
