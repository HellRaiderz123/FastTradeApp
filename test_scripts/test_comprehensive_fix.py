"""Comprehensive test of the fix"""

import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import date
import json

# Load .env
env_path = Path(__file__).parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path, override=True)

sys.path.insert(0, 'backend')

from app.core.broker.zerodha_symbols import build_zerodha_option_symbol
from app.core.market.expiry import format_zerodha_expiry, get_current_weekly_expiry
from app.core.market.ltp import get_ltp
from app.core.execution.zerodha import ZerodhaExecutionAdapter
from app.core.broker.zerodha.client import get_kite_client
from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent

print("\n" + "="*70)
print("COMPREHENSIVE FIX VERIFICATION TEST")
print("="*70)

tests_passed = 0
tests_total = 0

# Test 1: Expiry format
print("\n[TEST 1] Expiry Format")
tests_total += 1
expiry = date(2026, 2, 10)
formatted = format_zerodha_expiry(expiry)
expected = "26210"
if formatted == expected:
    print(f"  PASS: {expiry} -> {formatted}")
    tests_passed += 1
else:
    print(f"  FAIL: Expected {expected}, got {formatted}")

# Test 2: Symbol building
print("\n[TEST 2] Symbol Building")
tests_total += 1
symbol = build_zerodha_option_symbol(
    underlying="NIFTY",
    expiry=date(2026, 2, 10),
    strike=25800,
    option_type="PE"
)
expected_symbol = "NIFTY2621025800PE"
if symbol == expected_symbol:
    print(f"  PASS: {symbol}")
    tests_passed += 1
else:
    print(f"  FAIL: Expected {expected_symbol}, got {symbol}")

# Test 3: Weekly expiry selection
print("\n[TEST 3] Weekly Expiry Selection")
tests_total += 1
try:
    weekly = get_current_weekly_expiry("NIFTY")
    print(f"  PASS: Current NIFTY weekly expiry = {weekly}")
    tests_passed += 1
except Exception as e:
    print(f"  FAIL: {e}")

# Test 4: LTP Fetch
print("\n[TEST 4] LTP Fetch with Correct Symbol")
tests_total += 1
try:
    prices = get_ltp(["NIFTY2621025800PE", "NIFTY2621025700PE"])
    if prices and prices.get("NIFTY2621025800PE"):
        price_1 = prices["NIFTY2621025800PE"]
        price_2 = prices["NIFTY2621025700PE"]
        print(f"  PASS: Got LTP prices")
        print(f"    NIFTY2621025800PE: {price_1}")
        print(f"    NIFTY2621025700PE: {price_2}")
        tests_passed += 1
    else:
        print(f"  FAIL: No prices returned: {prices}")
except Exception as e:
    print(f"  FAIL: {type(e).__name__}: {str(e)[:50]}")

# Test 5: Entry Credit Calculation
print("\n[TEST 5] Entry Credit Calculation")
tests_total += 1
try:
    kite = get_kite_client()
    adapter = ZerodhaExecutionAdapter(kite_client=kite, dry_run=True)
    
    from app.db.models_intent import ExecutionIntent
    intent = ExecutionIntent()
    intent.run_id = "test"
    intent.intent_id = "test"
    intent.strategy = "BULL_PUT"
    intent.underlying = "NIFTY"
    intent.expiry = get_current_weekly_expiry("NIFTY")
    intent.ticket = {
        "strategy": "BULL_PUT",
        "underlying": "NIFTY",
        "lot_size": 65,
        "lots": 1,
        "legs": [
            {"side": "SELL", "strike": 25800, "type": "PE"},
            {"side": "BUY", "strike": 25700, "type": "PE"}
        ]
    }
    
    result = adapter.execute(intent)
    entry_credit = result.get("entry_credit", 0)
    
    if entry_credit and entry_credit > 0:
        print(f"  PASS: Entry credit = {entry_credit}")
        tests_passed += 1
        # Update intent with result for MTM test
        intent.execution_result = result
        intent.entry_credit = entry_credit
        intent.status = "EXECUTED"
        intent.ticket = intent.ticket  # Has prices now
    else:
        print(f"  FAIL: Entry credit is {entry_credit}")
        
except Exception as e:
    print(f"  FAIL: {type(e).__name__}: {str(e)[:50]}")

# Test 6: MTM Calculation
print("\n[TEST 6] MTM Calculation")
tests_total += 1
try:
    mtm = adapter.mtm(intent)
    print(f"  PASS: MTM calculated = {mtm:.2f}")
    tests_passed += 1
except Exception as e:
    print(f"  FAIL: {type(e).__name__}: {str(e)[:50]}")

# Test 7: Database symbol migration
print("\n[TEST 7] Database Symbol Updates")
tests_total += 1
try:
    db = SessionLocal()
    intents = db.query(ExecutionIntent).filter(
        ExecutionIntent.status.in_(['EXECUTED', 'CLOSED'])
    ).limit(5).all()
    
    symbols_fixed = 0
    for intent in intents:
        if intent.expiry and intent.ticket:
            for leg in intent.ticket.get("legs", []):
                sym = leg.get("symbol", "")
                # Check if symbol is in new format (has YY + single-digit M/D)
                if sym and not "FEB1" in sym and "262" in sym:
                    symbols_fixed += 1
    
    if symbols_fixed > 0:
        print(f"  PASS: Found {symbols_fixed} positions with corrected symbols")
        tests_passed += 1
    else:
        print(f"  FAIL: No corrected symbols found in DB")
    db.close()
except Exception as e:
    print(f"  FAIL: {e}")

# Summary
print("\n" + "="*70)
print(f"RESULTS: {tests_passed}/{tests_total} tests passed")
print("="*70 + "\n")

if tests_passed == tests_total:
    print("[OK] All tests passed! The fix is working correctly.")
    print("\nNext steps:")
    print("1. Test WebSocket connection: ws://localhost:8000/api/ws/positions")
    print("2. Create a new trade and verify position updates stream")
    print("3. Monitor MTM updates for real-time P&L")
else:
    print(f"[WARNING] {tests_total - tests_passed} tests failed")
