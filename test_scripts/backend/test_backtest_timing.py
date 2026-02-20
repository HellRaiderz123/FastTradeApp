"""
Test backtest timing to understand why it's fast
"""

import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.data.candles import get_historical_candles

print("\n" + "="*80)
print("BACKTEST TIMING ANALYSIS")
print("="*80)

# Test 1: Fetch candles and measure timing
start = time.time()
symbol = "NIFTY"
start_date = date(2024, 1, 1)
end_date = date(2024, 1, 31)

print(f"\n📊 Fetching {symbol} candles from {start_date} to {end_date}...")
print(f"   (Testing: Cache → API → Mock fallback chain)\n")

candles = get_historical_candles(symbol, start_date, end_date, "15minute")
elapsed = time.time() - start

print(f"✅ Fetched {len(candles)} candles in {elapsed:.3f}s")
print(f"   Rate: {len(candles)/elapsed:.0f} candles/sec")

if candles:
    # Check if these are mock or real candles
    first_candle = candles[0]
    print(f"\n📌 Sample candle (first):")
    print(f"   Timestamp: {first_candle.get('timestamp')}")
    print(f"   Close: {first_candle.get('close')}")
    print(f"   Open: {first_candle.get('open')}")
    print(f"   High: {first_candle.get('high')}")
    print(f"   Low: {first_candle.get('low')}")
    
    last_candle = candles[-1]
    print(f"\n📌 Sample candle (last):")
    print(f"   Timestamp: {last_candle.get('timestamp')}")
    print(f"   Close: {last_candle.get('close')}")
    
    # Check if prices are realistic NIFTY prices
    close_prices = [c.get('close', 0) for c in candles if c.get('close')]
    min_price = min(close_prices) if close_prices else 0
    max_price = max(close_prices) if close_prices else 0
    avg_price = sum(close_prices) / len(close_prices) if close_prices else 0
    
    print(f"\n📈 Price Statistics:")
    print(f"   Min: {min_price:.2f}")
    print(f"   Max: {max_price:.2f}")
    print(f"   Avg: {avg_price:.2f}")
    print(f"   Range: {max_price - min_price:.2f}")
    
    # Check if prices are realistic (NIFTY in Jan 2024 was ~20000-21000)
    if 19000 < avg_price < 23000:
        print(f"\n   ✅ Prices look realistic for NIFTY (Jan 2024)")
    else:
        print(f"\n   ❌ Prices don't look realistic for NIFTY (expected ~20000-21000, got {avg_price:.2f})")

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)
print("""
The backtest is fast because:
1. ✅ No API calls to Zerodha (if using cache or mock)
2. ✅ In-memory processing only
3. ✅ No network latency

To make backtest MORE REALISTIC:
1. ⏳ Implement Zerodha API integration (currently returning None)
2. ⏳ Test cache mechanism (save/load pickle)
3. ⏳ Compare mock prices vs real prices
""")
print("="*80 + "\n")
