"""Test get_ltp function"""

import sys
sys.path.insert(0, 'backend')

from app.core.market.ltp import get_ltp

print("Testing get_ltp() function")
print("=" * 70)

symbols = [
    "NIFTY26FEB1025800PE",
    "NIFTY26FEB1025700PE"
]

print(f"Fetching LTP for: {symbols}")
print()

try:
    result = get_ltp(symbols)
    print(f"Result: {result}")
    print(f"Type: {type(result)}")
    print()
    
    for sym in symbols:
        price = result.get(sym)
        print(f"  {sym}: {price}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
