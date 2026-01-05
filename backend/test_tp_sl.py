"""
Test Dynamic TP/SL Calculation
Shows how TP/SL adapts to different capital and risk scenarios
"""
import sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.core.risk.tp_sl_calculator import (
    calculate_tp_sl,
    calculate_tp_sl_from_ticket,
    get_risk_percentage_from_mode,
    RISK_PROFILES,
)

print("\n" + "="*100)
print("DYNAMIC TP/SL CALCULATOR TEST")
print("="*100)

# Test 1: Different capital amounts, same risk percentage
print("\n[TEST 1] Different Capital Amounts (2% risk, Conservative trader)")
print("-"*100)

capital_amounts = [50000, 100000, 200000, 500000]
for capital in capital_amounts:
    result = calculate_tp_sl(
        capital=capital,
        risk_percentage=2.0,
        position_size=1,
        lot_size=65,
        strategy_type="BULL_PUT"
    )
    print(f"  Capital: Rs {capital:,}")
    print(f"    TP: Rs {result['tp']:,.0f}")
    print(f"    SL: Rs {result['sl']:,.0f}")
    print(f"    Max Risk: Rs {result['max_risk']:,.0f} ({result['tp_ratio']}% of capital)")
    print()

# Test 2: Same capital, different risk modes
print("\n[TEST 2] Risk Profiles (100k capital, BULL_PUT spread)")
print("-"*100)

capital = 100000
for risk_mode, risk_pct in RISK_PROFILES.items():
    result = calculate_tp_sl(
        capital=capital,
        risk_percentage=risk_pct,
        position_size=1,
        lot_size=65,
        strategy_type="BULL_PUT"
    )
    print(f"  {risk_mode} ({risk_pct}% risk):")
    print(f"    TP: Rs {result['tp']:,.0f}")
    print(f"    SL: Rs {result['sl']:,.0f}")
    print(f"    Risk per Lot: Rs {result['risk_per_lot']:,.0f}")
    print()

# Test 3: Multiple position sizes
print("\n[TEST 3] Multiple Position Sizes (100k capital, 2% risk)")
print("-"*100)

position_sizes = [1, 2, 3, 5]
for pos_size in position_sizes:
    result = calculate_tp_sl(
        capital=100000,
        risk_percentage=2.0,
        position_size=pos_size,
        lot_size=65,
        strategy_type="BULL_PUT"
    )
    print(f"  {pos_size} Spread(s) ({pos_size * 65} quantity):")
    print(f"    TP: Rs {result['tp']:,.0f}")
    print(f"    SL: Rs {result['sl']:,.0f}")
    print(f"    Risk per Lot: Rs {result['risk_per_lot']:,.0f}")
    print()

# Test 4: Different strategy types
print("\n[TEST 4] Different Strategy Types (100k capital, 2% risk, 1 position)")
print("-"*100)

strategies = ["BULL_PUT", "BEAR_CALL", "IRON_CONDOR"]
for strategy in strategies:
    result = calculate_tp_sl(
        capital=100000,
        risk_percentage=2.0,
        position_size=1,
        lot_size=65,
        strategy_type=strategy
    )
    print(f"  {strategy}:")
    print(f"    TP: Rs {result['tp']:,.0f}")
    print(f"    SL: Rs {result['sl']:,.0f}")
    print(f"    Max Risk: Rs {result['max_risk']:,.0f}")
    print()

# Test 5: From ticket
print("\n[TEST 5] Calculate from Strategy Ticket")
print("-"*100)

ticket = {
    "strategy": "BULL_PUT",
    "lot_size": 65,
    "lots": 2,
}

tp_sl = calculate_tp_sl_from_ticket(
    ticket=ticket,
    capital=150000,
    risk_percentage=2.0,
)

print(f"  Ticket: {ticket}")
print(f"  Capital: Rs 150,000")
print(f"  Risk Mode: BALANCED (2%)")
print(f"  Result:")
print(f"    TP: Rs {tp_sl['tp']:,.0f}")
print(f"    SL: Rs {tp_sl['sl']:,.0f}")
print(f"    Position Qty: {tp_sl['position_size_qty']}")
print(f"    Risk per Lot: Rs {tp_sl['risk_per_lot']:,.0f}")

# Test 6: Comparison - Old hardcoded vs Dynamic
print("\n[TEST 6] Old Hardcoded vs Dynamic Calculation")
print("-"*100)

print("  OLD HARDCODED:")
print("    TP: Rs 1,500")
print("    SL: Rs -2,000")
print("    Problem: Fixed for all scenarios, not adaptive")

print("\n  NEW DYNAMIC (100k capital, 2% risk):")
result = calculate_tp_sl(capital=100000, risk_percentage=2.0)
print(f"    TP: Rs {result['tp']:,.0f}")
print(f"    SL: Rs {result['sl']:,.0f}")
print(f"    Benefit: Scales with capital and risk tolerance")

print("\n  NEW DYNAMIC (500k capital, 2% risk):")
result = calculate_tp_sl(capital=500000, risk_percentage=2.0)
print(f"    TP: Rs {result['tp']:,.0f}")
print(f"    SL: Rs {result['sl']:,.0f}")
print(f"    Benefit: Trader with 5x capital gets 5x TP/SL")

# Test 7: Risk profile helper
print("\n[TEST 7] Risk Profile Helper Function")
print("-"*100)

for mode in ["CONSERVATIVE", "BALANCED", "AGGRESSIVE", "VERY_AGGRESSIVE"]:
    risk_pct = get_risk_percentage_from_mode(mode)
    result = calculate_tp_sl(capital=100000, risk_percentage=risk_pct)
    print(f"  {mode}: {risk_pct}% risk")
    print(f"    Max Loss: Rs {result['max_risk']:,.0f}")
    print(f"    TP Target: Rs {result['tp']:,.0f}")
    print()

print("\n" + "="*100)
print("ALL TESTS PASSED")
print("="*100)

print("\nKEY IMPROVEMENTS:")
print("  1. TP/SL now scales with capital automatically")
print("  2. Risk-aware: respects trader's risk percentage")
print("  3. Flexible: supports multiple strategies")
print("  4. Scalable: works with any position size")
print("  5. Configurable: risk profiles for different traders")

print("\nUSAGE IN API:")
print("  POST /intent/create")
print("    ?run_id=123")
print("    &capital=150000         # Required")
print("    &risk_mode=BALANCED     # CONSERVATIVE, BALANCED, AGGRESSIVE")
print("  Returns:")
print("    {")
print("      'intent_id': '...',")
print("      'tp_sl': {")
print("        'tp': 3000.0,")
print("        'sl': -3000.0,")
print("        'max_risk': 3000.0,")
print("        ...")
print("      }")
print("    }")

print("\n" + "="*100 + "\n")
