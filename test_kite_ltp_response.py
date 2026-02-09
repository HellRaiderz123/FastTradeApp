"""Test what Zerodha kite.ltp() actually returns"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path, override=True)

sys.path.insert(0, 'backend')

from app.core.broker.zerodha.client import get_kite_client
import json

print("="*70)
print("TESTING kite.ltp() RESPONSE FORMAT")
print("="*70)

try:
    kite = get_kite_client()
    print("✅ Kite client initialized")
    print()
    
    # Test with some NIFTY options
    symbols = ["NFO:NIFTY26FEB1025800PE", "NFO:NIFTY26FEB1025700PE"]
    
    print(f"Fetching LTP for: {symbols}")
    result = kite.ltp(symbols)
    
    print(f"\nResponse type: {type(result)}")
    print(f"Response keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
    print()
    
    print("Full response:")
    print(json.dumps(result, indent=2, default=str))
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
