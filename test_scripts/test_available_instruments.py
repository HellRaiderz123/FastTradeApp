"""List available option instruments from Zerodha"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path, override=True)

sys.path.insert(0, 'backend')

from app.core.broker.zerodha.instruments import load_instruments
from app.core.broker.zerodha.client import get_kite_client

print("="*70)
print("CHECKING AVAILABLE NIFTY INSTRUMENTS")
print("="*70)

try:
    print("\nLoading instruments from Zerodha...")
    df = load_instruments(exchange="NFO")
    print(f"✅ Loaded {len(df)} instruments")
    
    # Filter for NIFTY options
    nifty_ce = df[(df['name'] == 'NIFTY') & (df['instrument_type'] == 'CE')]
    
    print(f"\nNIFTY CE (Call) instruments: {len(nifty_ce)}")
    if len(nifty_ce) > 0:
        print("First 10:")
        for idx, row in nifty_ce.head(10).iterrows():
            print(f"  {row['tradingsymbol']:<20} expiry={row.get('expiry'):<10} strike={row.get('strike')}")
    
    # Try to get LTP for the first one
    if len(nifty_ce) > 0:
        first_sym = nifty_ce.iloc[0]['tradingsymbol']
        print(f"\nTrying LTP for first available: {first_sym}")
        kite = get_kite_client()
        result = kite.ltp([f"NFO:{first_sym}"])
        print(f"  Result: {result}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
