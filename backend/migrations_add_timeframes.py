"""
Migration script to add multi-timeframe candle tables.
Creates tables for 1m, 5m, and 1h candles (15m and daily already exist).
"""
from sqlalchemy import create_engine
from app.db.session import Base, DATABASE_URL
from app.db.models_candles import Candle1m, Candle5m, Candle1h

def run_migration():
    """Create the multi-timeframe candle tables"""
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    
    print("Creating multi-timeframe candle tables...")
    print("- candles_1m")
    print("- candles_5m")
    print("- candles_1h")
    
    # Create tables
    Base.metadata.create_all(bind=engine, tables=[
        Candle1m.__table__,
        Candle5m.__table__,
        Candle1h.__table__,
    ])
    
    print("✅ Migration complete!")
    print("\nNew tables created:")
    print("  • candles_1m  - 1-minute candlestick data")
    print("  • candles_5m  - 5-minute candlestick data")
    print("  • candles_1h  - 1-hour candlestick data")
    print("\nExisting tables:")
    print("  • candles_15m - 15-minute candlestick data")
    print("  • candles_daily - Daily candlestick data")

if __name__ == "__main__":
    run_migration()
