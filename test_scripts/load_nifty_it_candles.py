#!/usr/bin/env python3
"""
Load NIFTY_IT candles from Zerodha and populate the database.
This solves the "Not enough candles" error for NIFTY_IT.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.db.session import SessionLocal
from app.core.market.candles import fetch_15m_candles
from app.db.models_candles import Candle15m

def load_nifty_it_candles(days: int = 30):
    """
    Load NIFTY_IT 15-minute candles from Zerodha.
    
    Args:
        days: How many days of historical data to load (default 30)
    """
    print("=" * 70)
    print("Loading NIFTY_IT Candles from Zerodha")
    print("=" * 70)
    print()
    
    db = SessionLocal()
    try:
        # Check current status
        current_count = db.query(Candle15m).filter(Candle15m.symbol == "NIFTY_IT").count()
        print(f"1️⃣ Current NIFTY_IT candles in DB: {current_count}")
        print(f"   Need minimum: 100 candles")
        
        if current_count >= 100:
            print(f"   ✅ Already sufficient!")
            return
        
        print()
        print(f"2️⃣ Fetching last {days} days of NIFTY_IT data from Zerodha...")
        print(f"   This will add ~{days * 26} candles (26 per trading day)")
        print()
        
        # Fetch the data
        fetch_15m_candles(db, "NIFTY_IT", days=days)
        
        print()
        print("3️⃣ Verifying...")
        new_count = db.query(Candle15m).filter(Candle15m.symbol == "NIFTY_IT").count()
        added = new_count - current_count
        
        if new_count > 0:
            oldest = db.query(Candle15m).filter(Candle15m.symbol == "NIFTY_IT").order_by(Candle15m.timestamp.asc()).first()
            newest = db.query(Candle15m).filter(Candle15m.symbol == "NIFTY_IT").order_by(Candle15m.timestamp.desc()).first()
            
            print(f"   Total NIFTY_IT candles now: {new_count}")
            print(f"   Added: {added} new candles")
            print()
            print(f"   Date range: {oldest.timestamp.date()} to {newest.timestamp.date()}")
            print()
            
            if new_count >= 100:
                print("   ✅ SUCCESS! NIFTY_IT now has {new_count} candles")
                print(f"   ✅ You can now generate signals for NIFTY_IT")
                print()
                print("   Next steps:")
                print("   1. Refresh the suggestions endpoint")
                print("   2. NIFTY_IT should now show a valid signal instead of 'Not enough candles'")
            else:
                print(f"   ⚠️  Still not enough ({new_count} < 100)")
                print(f"   Try loading more days: --days {30 + (100 - new_count) // 26}")
        else:
            print("   ❌ No candles loaded - check your Zerodha connection")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30, help="Number of days to load (default 30)")
    args = parser.parse_args()
    
    load_nifty_it_candles(days=args.days)
