"""Test with different symbols and check for errors"""

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
print("TESTING DIFFERENT SYMBOL FORMATS")
print("="*70)

try:
    kite = get_kite_client()
    print("✅ Kite client initialized\n")
    
    test_cases = [
        {
            "name": "Future NIFTY indices (Feb 2026)",
            "symbols": ["NFO:NIFTY26FEB1025800PE", "NFO:NIFTY26FEB1025700PE"],
        },
        {
            "name": "Current month NIFTY",
            "symbols": ["NFO:NIFTY25NOV25800PE", "NFO:NIFTY25NOV25700PE"],
        },
        {
            "name": "NIFTY spot",
            "symbols": ["NSE:NIFTY50"],
        },
        {
            "name": "NIFTY index",
            "symbols": ["NSE:NIFTY 50"],
        },
    ]
    
    for test in test_cases:
        print(f"\n{test['name']}:")
        print(f"  Symbols: {test['symbols']}")
        try:
            result = kite.ltp(test['symbols'])
            print(f"  Result: {result}")
            if result:
                for k, v in result.items():
                    print(f"    {k}: {v}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
