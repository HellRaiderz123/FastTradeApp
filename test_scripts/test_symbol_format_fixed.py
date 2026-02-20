"""Test that symbol format is now correct"""

import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import date

# Load .env
env_path = Path(__file__).parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path, override=True)

sys.path.insert(0, 'backend')

from app.core.broker.zerodha_symbols import build_zerodha_option_symbol
from app.core.market.expiry import format_zerodha_expiry, get_current_weekly_expiry

print("="*70)
print("TESTING SYMBOL FORMAT")
print("="*70)

# Test with Feb 10, 2026 (weekly NIFTY)
expiry = date(2026, 2, 10)
formatted = format_zerodha_expiry(expiry)
print(f"\nExpiry: {expiry}")
print(f"Formatted: {formatted}")
print(f"Expected: 26210")
print(f"✅ CORRECT" if formatted == "26210" else f"❌ WRONG - got {formatted}")

# Build full symbol
symbol = build_zerodha_option_symbol(
    underlying="NIFTY",
    expiry=expiry,
    strike=25800,
    option_type="PE"
)
print(f"\nBuilt symbol: {symbol}")
print(f"Expected: NIFTY2621025800PE")
print(f"✅ CORRECT" if symbol == "NIFTY2621025800PE" else f"❌ WRONG - got {symbol}" )

# Now test current weekly expiry
print(f"\n{'='*70}")
print("CURRENT WEEKLY EXPIRY")
print(f"{'='*70}")

current_weekly = get_current_weekly_expiry("NIFTY")
print(f"\nCurrent NIFTY weekly expiry: {current_weekly}")
formatted_current = format_zerodha_expiry(current_weekly)
print(f"Formatted: {formatted_current}")

symbol_current = build_zerodha_option_symbol(
    underlying="NIFTY",
    expiry=current_weekly,
    strike=25800,
    option_type="PE"
)
print(f"Symbol: {symbol_current}")

# Test against actual Zerodha
print(f"\n{'='*70}")
print("VERIFY AGAINST ZERODHA INSTRUMENTS")
print(f"{'='*70}")

from app.core.broker.zerodha.instruments import load_instruments
df = load_instruments()

# Look for symbols with our strike and type
nifty_straddle = df[
    (df['name'] == 'NIFTY') & 
    (df['strike'] == 25800) & 
    (df['instrument_type'] == 'PE')
]

print(f"\nNIFTY 25800 PE options in Zerodha ({len(nifty_straddle)} found):")
for idx, row in nifty_straddle.head(3).iterrows():
    print(f"  Symbol: {row['tradingsymbol']:<20} Expiry: {row['expiry']}")

print("\n" + "="*70)
