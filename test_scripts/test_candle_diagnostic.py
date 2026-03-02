#!/usr/bin/env python3
"""
Diagnose why NIFTY_IT doesn't have enough candles for signal generation.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.db.session import SessionLocal
from app.db.models_candles import Candle15m
from datetime import datetime, timedelta

def diagnose_candles():
    """Check candle counts for all symbols."""
    print("=" * 70)
    print("Candle Data Diagnostic")
    print("=" * 70)
    print()
    
    db = SessionLocal()
    try:
        # Get all unique symbols
        print("1️⃣ Symbols in Candle15m table:")
        symbols = db.query(Candle15m.symbol).distinct().all()
        symbols_list = sorted([s[0] for s in symbols])
        print(f"   Total unique symbols: {len(symbols_list)}")
        print(f"   Symbols: {', '.join(symbols_list[:10])}")
        if len(symbols_list) > 10:
            print(f"   ... and {len(symbols_list) - 10} more")
        print()
        
        # Check candle counts for key symbols
        print("2️⃣ Candle counts by symbol:")
        test_symbols = ["NIFTY", "BANKNIFTY", "FINNIFTY", "NIFTY_IT"]
        
        for symbol in test_symbols:
            count = db.query(Candle15m).filter(Candle15m.symbol == symbol).count()
            
            if count > 0:
                # Get date range
                first = db.query(Candle15m).filter(Candle15m.symbol == symbol).order_by(Candle15m.timestamp.asc()).first()
                last = db.query(Candle15m).filter(Candle15m.symbol == symbol).order_by(Candle15m.timestamp.desc()).first()
                
                date_range = "N/A"
                if first and last:
                    date_range = f"{first.timestamp.date()} to {last.timestamp.date()}"
                
                status = "✅" if count >= 100 else "❌"
                print(f"   {status} {symbol:15} {count:6} candles  ({date_range})")
            else:
                print(f"   ❌ {symbol:15} NO DATA")
        print()
        
        # Analyze NIFTY_IT specifically
        print("3️⃣ NIFTY_IT Candle Analysis:")
        nifty_it_count = db.query(Candle15m).filter(Candle15m.symbol == "NIFTY_IT").count()
        
        if nifty_it_count > 0:
            oldest = db.query(Candle15m).filter(Candle15m.symbol == "NIFTY_IT").order_by(Candle15m.timestamp.asc()).first()
            newest = db.query(Candle15m).filter(Candle15m.symbol == "NIFTY_IT").order_by(Candle15m.timestamp.desc()).first()
            
            print(f"   Total candles: {nifty_it_count}")
            print(f"   Required for signal: 100")
            print(f"   Status: {'✅ SUFFICIENT' if nifty_it_count >= 100 else '❌ INSUFFICIENT'}")
            print()
            print(f"   Oldest candle: {oldest.timestamp} (close: {oldest.close})")
            print(f"   Newest candle: {newest.timestamp} (close: {newest.close})")
            
            # Calculate age of data
            now = datetime.utcnow()
            time_span = newest.timestamp - oldest.timestamp
            print(f"   Time span: {time_span}")
            
            # Estimate how many 15-min candles per day
            candles_per_day = 26  # 6.5 hours * 4 candles/hour (approximately)
            days_of_data = nifty_it_count / candles_per_day
            print(f"   Days of data: {days_of_data:.1f} days")
            print()
            
            if nifty_it_count < 100:
                needed = 100 - nifty_it_count
                print(f"   ⚠️ Need {needed} more candles ({needed/candles_per_day:.1f} more days of trading)")
        else:
            print(f"   ❌ No NIFTY_IT candles in database!")
            print(f"   ⚠️ Data needs to be fetched/cached first")
        
        print()
        print("=" * 70)
        print("Why NIFTY_IT shows 'Not enough candles':")
        print("=" * 70)
        print("1. Candle data is fetched from Zerodha API or cached source")
        print("2. NIFTY_IT may not have been actively tracked yet")
        print("3. System requires 100+ candles for reliable technical analysis")
        print("4. Each 15-min candle ≈ ~4 per hour, ~26 per trading day")
        print("5. To get 100 candles = ~4 days of continuous market data")
        print()
        print("Solutions:")
        print("  Option 1: Wait for more candles to accumulate (~4 trading days)")
        print("  Option 2: Pre-load historical data via Zerodha API")
        print("  Option 3: Lower minimum candle requirement (currently 100)")
        
    finally:
        db.close()

if __name__ == "__main__":
    diagnose_candles()
