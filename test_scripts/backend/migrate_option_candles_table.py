"""
Migration: Create option_historical_candles table for backtest data
Run this to enable historical option backtesting
"""

import logging
from sqlalchemy import text
from app.db.session import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Create option_historical_candles table"""
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS option_historical_candles (
        id SERIAL PRIMARY KEY,
        tradingsymbol VARCHAR NOT NULL,
        instrument_token INTEGER NOT NULL,
        underlying VARCHAR NOT NULL,
        expiry DATE NOT NULL,
        strike REAL NOT NULL,
        option_type VARCHAR NOT NULL,
        timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume REAL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    CREATE INDEX IF NOT EXISTS ix_option_candles_symbol_ts 
        ON option_historical_candles(tradingsymbol, timestamp);
    
    CREATE UNIQUE INDEX IF NOT EXISTS ix_option_candles_unique 
        ON option_historical_candles(tradingsymbol, timestamp);
    
    CREATE INDEX IF NOT EXISTS ix_option_candles_expiry_strike 
        ON option_historical_candles(underlying, expiry, strike, option_type);
    
    CREATE INDEX IF NOT EXISTS ix_option_candles_underlying 
        ON option_historical_candles(underlying);
    
    CREATE INDEX IF NOT EXISTS ix_option_candles_expiry 
        ON option_historical_candles(expiry);
    """
    
    try:
        with engine.connect() as conn:
            logger.info("Creating option_historical_candles table...")
            conn.execute(text(create_table_sql))
            conn.commit()
            logger.info("✅ Migration complete!")
            
            # Check if table exists
            result = conn.execute(text("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_name = 'option_historical_candles'
            """))
            count = result.scalar()
            
            if count > 0:
                logger.info("✅ Table verified successfully")
            else:
                logger.error("❌ Table creation may have failed")
                
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


if __name__ == "__main__":
    run_migration()
