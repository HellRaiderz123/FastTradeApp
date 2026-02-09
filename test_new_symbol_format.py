"""Test that new symbol building works correctly"""

import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import date

# Load .env
env_path = Path(__file__).parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path, override=True)

sys.path.insert(0, 'backend')

from app.core.broker.zerodha_symbols import build_zerodha_option_symbol

print("="*70)
print("TESTING NEW SYMBOL BUILDING")
print("="*70)

test_cases = [
    {
        "underlying": "NIFTY",
        "expiry": date(2026, 2, 10),  # Weekly (Feb 10)
        "strike": 25800,
        "option_type": "PE",
        "expected": "NIFTY2621025800PE"
    },
    {
        "underlying": "NIFTY",
        "expiry": date(2026, 2, 17),  # Weekly (Feb 17)
        "strike": 25700,
        "option_type": "CE",
        "expected": "NIFTY2621725700CE"
    },
    {
        "underlying": "BANKNIFTY",
        "expiry": date(2026, 2, 18),  # Weekly Wednesday (Feb 18)
        "strike": 50000,
        "option_type": "PE",
        "expected": "BANKNIFTY2621850000PE"  # Strike is 50000 so symbol has 50000
    },
]

print()
for i, test in enumerate(test_cases, 1):
    symbol = build_zerodha_option_symbol(
        underlying=test["underlying"],
        expiry=test["expiry"],
        strike=test["strike"],
        option_type=test["option_type"]
    )
    
    match = symbol == test["expected"]
    status = "[OK]" if match else "[FAIL]"
    
    print(f"{status} Test {i}:")
    print(f"  Built:    {symbol}")
    print(f"  Expected: {test['expected']}")
    print()

print("="*70)
