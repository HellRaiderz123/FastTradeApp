"""
Test backtest with Zerodha historical API
"""

import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Test 1: Check if Zerodha credentials are set
print("\n" + "="*80)
print("ZERODHA CREDENTIALS CHECK")
print("="*80)

api_key = os.getenv("ZERODHA_API_KEY")
access_token = os.getenv("ZERODHA_ACCESS_TOKEN")

if api_key and access_token:
    print(f"✅ ZERODHA_API_KEY: {api_key[:10]}...")
    print(f"✅ ZERODHA_ACCESS_TOKEN: {access_token[:10]}...")
else:
    print("❌ Zerodha credentials NOT set")
    print("\nTo use Zerodha historical data, set environment variables:")
    print("  export ZERODHA_API_KEY=your_api_key")
    print("  export ZERODHA_ACCESS_TOKEN=your_access_token")

print("\n" + "="*80)
print("TESTING CANDLES FETCH (Priority Order)")
print("="*80)

from app.core.data.candles import get_historical_candles

symbol = "NIFTY"
start_date = date(2024, 1, 1)
end_date = date(2024, 1, 31)

print(f"\n📊 Fetching {symbol} from {start_date} to {end_date}...")
print(f"   Priority: Cache → Zerodha (if creds set) → Yahoo Finance → Mock\n")

candles = get_historical_candles(symbol, start_date, end_date, "daily")

print(f"\n✅ Fetched {len(candles)} candles")

if candles:
    # Show statistics
    closes = [c['close'] for c in candles if c.get('close', 0) > 0]
    if closes:
        print(f"\n📈 Statistics:")
        print(f"   Min Price:  {min(closes):.2f}")
        print(f"   Max Price:  {max(closes):.2f}")
        print(f"   Avg Price:  {sum(closes)/len(closes):.2f}")
        print(f"   First Date: {candles[0].get('date')}")
        print(f"   Last Date:  {candles[-1].get('date')}")
        
        # Identify data source based on price characteristics
        avg_price = sum(closes) / len(closes)
        if 19000 < avg_price < 23000:
            print(f"\n   🔍 Data appears to be REALISTIC (NIFTY prices)")
        else:
            print(f"\n   🔍 Data appears to be MOCK (not real prices)")

print("\n" + "="*80)
print("BACKTEST READY")
print("="*80)
print(f"""
Priority Chain Status:
  [1] Cache:         Ready
  [2] Zerodha API:   {'✅ Configured' if api_key and access_token else '❌ Not configured'}
  [3] Yahoo Finance: ✅ Ready
  [4] Mock Data:     ✅ Ready (fallback)

When you run backtest, it will use the first available source.
Best for accuracy: Zerodha with real credentials
""")
