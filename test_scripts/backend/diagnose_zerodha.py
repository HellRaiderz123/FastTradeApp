#!/usr/bin/env python3
"""
Diagnose Zerodha API connectivity issues.
"""

import logging
from app.core.broker.zerodha.client import get_kite_client
from app.core.broker.zerodha.instruments import get_index_token, load_instruments

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("\n" + "="*60)
print("ZERODHA API DIAGNOSTIC")
print("="*60)

# Test 1: Client initialization
print("\n[1] Testing Kite Client Initialization...")
try:
    kite = get_kite_client()
    print("✅ Kite client initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize Kite client: {e}")
    exit(1)

# Test 2: Get token for NIFTY
print("\n[2] Testing Index Token Retrieval...")
try:
    token = get_index_token("NIFTY")
    print(f"✅ NIFTY token: {token} (type: {type(token).__name__})")
except Exception as e:
    print(f"❌ Failed to get token: {e}")
    exit(1)

# Test 3: Test LTP call
print("\n[3] Testing LTP API Call...")
try:
    data = kite.ltp([token])
    print(f"✅ LTP API successful")
    print(f"   Response type: {type(data).__name__}")
    print(f"   Response keys: {list(data.keys())}")
    
    # Check data format
    for key, value in list(data.items())[:1]:
        print(f"   Key: {key} (type: {type(key).__name__})")
        print(f"   Value: {value}")
        if isinstance(value, dict):
            print(f"   Value keys: {list(value.keys())}")
except Exception as e:
    print(f"❌ LTP API failed: {e}")
    print(f"   Error type: {type(e).__name__}")
    import traceback
    traceback.print_exc()

# Test 4: Test instruments load
print("\n[4] Testing Instruments Load...")
try:
    instruments = load_instruments()
    print(f"✅ Instruments loaded: {len(instruments)} records")
    if not instruments.empty:
        print(f"   Columns: {list(instruments.columns)}")
        print(f"   Sample NIFTY records:")
        nifty_sample = instruments[instruments["name"] == "NIFTY"].head(3)
        if not nifty_sample.empty:
            print(nifty_sample[["name", "strike", "instrument_type", "expiry"]].to_string())
except Exception as e:
    print(f"❌ Instruments load failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("DIAGNOSTIC COMPLETE")
print("="*60)
print("\nCommon Issues:")
print("1. Access token expired → Re-authenticate with Zerodha")
print("2. Wrong API key → Verify ZERODHA_API_KEY in .env")
print("3. Network issue → Check internet connection")
print("4. Market closed → Try during market hours (9:15-15:30 IST)")
print()
