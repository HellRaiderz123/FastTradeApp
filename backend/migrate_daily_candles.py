"""
Migration: Add CandleDaily table for swing trading
Creates a new table to store daily candles for stocks.
"""

import sys
from sqlalchemy import create_engine, inspect
from app.db.session import engine, Base
from app.db.models_candles import CandleDaily

def migrate():
    print("🔧 Running migration: Add CandleDaily table...")
    
    # Create inspector to check existing tables
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    if "candles_daily" in existing_tables:
        print("✅ Table 'candles_daily' already exists. Skipping.")
        return
    
    # Create the new table
    try:
        CandleDaily.__table__.create(engine)
        print("✅ Created table: candles_daily")
        print("   Columns: id, symbol, date, open, high, low, close, volume, created_at")
        print("   Index: ix_candles_daily_symbol_date (unique)")
    except Exception as e:
        print(f"❌ Failed to create table: {e}")
        sys.exit(1)
    
    print("\n✅ Migration completed successfully!")
    print("\n📝 Next steps:")
    print("   1. Daily candles table is ready")
    print("   2. Use Zerodha API to fetch historical daily candles")
    print("   3. Swing strategies will use EMA 50/200 on daily data")
    print("   4. Frontend toggle switches between intraday (15m) and swing (daily)")

if __name__ == "__main__":
    migrate()
