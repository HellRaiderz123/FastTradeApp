"""Test LTP fetching with corrected symbols"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path, override=True)

sys.path.insert(0, 'backend')

from app.core.broker.zerodha.client import get_kite_client
from app.core.market.ltp import get_ltp

print("="*70)
print("TESTING LTP WITH CORRECTED SYMBOLS")
print("="*70)

try:
    kite = get_kite_client()
    print("✅ Kite client initialized\n")
    
    # Use the CORRECT symbol that matches Zerodha
    symbols = ["NIFTY2621025800PE", "NIFTY2621025700PE"]
    
    print(f"Testing get_ltp() with corrected symbols:")
    print(f"  {symbols}\n")
    
    result = get_ltp(symbols)
    print(f"Result: {result}")
    print()
    
    for sym in symbols:
        price = result.get(sym, "NOT FOUND")
        print(f"  {sym}: {price}")
    
    # Also test direct kite.ltp()
    print(f"\n{'='*70}")
    print("Direct kite.ltp() call:")
    print(f"{'='*70}\n")
    
    nfo_symbols = [f"NFO:{sym}" for sym in symbols]
    direct_result = kite.ltp(nfo_symbols)
    print(f"Result: {direct_result}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
