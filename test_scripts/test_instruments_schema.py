"""Check what's in the instruments dataframe"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path, override=True)

sys.path.insert(0, 'backend')

from app.core.broker.zerodha.instruments import load_instruments

print("="*70)
print("INSTRUMENTS DATAFRAME SCHEMA")
print("="*70)

try:
    df = load_instruments(exchange="NFO")
    
    print(f"\nColumns: {list(df.columns)}")
    print(f"\nTotal records: {len(df)}")
    
    # Show a sample NIFTY CE record
    nifty_ce = df[(df['name'] == 'NIFTY') & (df['instrument_type'] == 'CE')].head(1)
    if len(nifty_ce) > 0:
        print("\nSample NIFTY CE (call) record:")
        row = nifty_ce.iloc[0]
        for col in df.columns:
            print(f"  {col:<20} {row[col]}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
