"""
Daily job to archive option chain candles before expiry
Run this via cron/scheduler to build historical option data database
"""

import logging
from datetime import date, datetime, timedelta
from app.core.broker.zerodha.client import get_kite_client
from app.core.broker.zerodha.instruments import load_instruments
from app.db.session import SessionLocal
from app.db.models import OptionHistoricalCandle  # You need to create this model

logger = logging.getLogger(__name__)


def store_option_candles_for_expiry(underlying: str, expiry: date):
    """
    Fetch and store 15-min candles for all strikes of an expiry
    Run this daily starting 7 days before expiry
    """
    db = SessionLocal()
    kite = get_kite_client()
    
    try:
        # Get all option contracts for this expiry
        instruments = load_instruments(exchange="NFO")
        options = instruments[
            (instruments['name'] == underlying) &
            (instruments['expiry'] == expiry) &
            (instruments['instrument_type'].isin(['CE', 'PE']))
        ]
        
        logger.info(f"Found {len(options)} option contracts for {underlying} {expiry}")
        
        # Fetch last 7 days of candles for each
        from_dt = datetime.now() - timedelta(days=7)
        to_dt = datetime.now()
        
        for _, opt in options.iterrows():
            try:
                symbol = opt['tradingsymbol']
                token = opt['instrument_token']
                
                # Fetch historical data
                candles = kite.historical_data(
                    instrument_token=token,
                    from_date=from_dt,
                    to_date=to_dt,
                    interval="15minute"
                )
                
                # Store in database
                for candle in candles:
                    db_candle = OptionHistoricalCandle(
                        tradingsymbol=symbol,
                        instrument_token=token,
                        underlying=underlying,
                        expiry=expiry,
                        strike=opt['strike'],
                        option_type=opt['instrument_type'],
                        timestamp=candle['date'],
                        open=candle['open'],
                        high=candle['high'],
                        low=candle['low'],
                        close=candle['close'],
                        volume=candle['volume'],
                    )
                    db.merge(db_candle)  # Update if exists
                
                db.commit()
                logger.info(f"✅ Stored {len(candles)} candles for {symbol}")
                
            except Exception as e:
                logger.error(f"Failed to store {opt['tradingsymbol']}: {e}")
                continue
        
    finally:
        db.close()


def daily_archive_job():
    """
    Run this daily to archive option chains for upcoming expiries
    Store data for current + next 2 weeks expiries
    """
    from app.core.market.expiry import get_weekly_expiry_for_date
    
    today = date.today()
    
    for underlying in ['NIFTY', 'BANKNIFTY', 'FINNIFTY']:
        for weeks_ahead in range(3):  # Current + next 2 weeks
            target_date = today + timedelta(weeks=weeks_ahead)
            expiry = get_weekly_expiry_for_date(underlying, target_date)
            
            logger.info(f"Archiving option chain: {underlying} {expiry}")
            store_option_candles_for_expiry(underlying, expiry)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    daily_archive_job()
