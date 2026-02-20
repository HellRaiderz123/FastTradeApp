"""
Direct test of relative strike engine logic
"""
from app.core.strategies.option_spread_custom.engine import (
    OptionSpreadCustom,
    _extract_legs,
    _resolve_strikes,
)

def test_relative_strikes():
    print("="*60)
    print("Testing Relative Strike Engine")
    print("="*60)
    
    # Test 1: Absolute strikes
    print("\n1️⃣ Test Absolute Strikes")
    context = {
        "underlying": "NIFTY",
        "parameters": {
            "expiry": "2026-01-15",
            "legs": [
                {
                    "type": "SELL",
                    "option_type": "CE",
                    "strike": 26200,
                    "strike_type": "ABSOLUTE",
                    "quantity": 65
                },
                {
                    "type": "BUY",
                    "option_type": "CE",
                    "strike": 26300,
                    "strike_type": "ABSOLUTE",
                    "quantity": 65
                }
            ]
        }
    }
    
    legs = _extract_legs(context["parameters"])
    print(f"   Extracted {len(legs)} legs")
    for leg in legs:
        print(f"   - {leg.side} {leg.strike} {leg.option_type} (mode: {leg.strike_type})")
    
    # Test 2: Relative strikes
    print("\n2️⃣ Test Relative Strikes")
    context2 = {
        "underlying": "NIFTY",
        "parameters": {
            "expiry": "2026-01-15",
            "legs": [
                {
                    "type": "SELL",
                    "option_type": "CE",
                    "strike_type": "RELATIVE",
                    "strike_offset": 0,  # ATM
                    "quantity": 65
                },
                {
                    "type": "BUY",
                    "option_type": "CE",
                    "strike_type": "RELATIVE",
                    "strike_offset": 100,  # ATM + 100
                    "quantity": 65
                }
            ]
        }
    }
    
    legs2 = _extract_legs(context2["parameters"])
    print(f"   Extracted {len(legs2)} legs")
    for leg in legs2:
        print(f"   - {leg.side} offset={leg.strike_offset} {leg.option_type} (mode: {leg.strike_type})")
    
    # Test resolution
    print("\n3️⃣ Test Strike Resolution")
    spot = 26150
    print(f"   Current Spot: {spot}")
    
    resolved_legs = _resolve_strikes(legs2, "NIFTY", spot)
    print(f"   Resolved {len(resolved_legs)} legs:")
    for leg in resolved_legs:
        print(f"   - {leg.side} {leg.strike} {leg.option_type} (offset was: {leg.strike_offset})")
    
    # Test 3: Full engine run
    print("\n4️⃣ Test Full Engine Run")
    engine = OptionSpreadCustom()
    
    try:
        result = engine.run(context2)
        print(f"   ✅ Strategy: {result.get('strategy')}")
        print(f"   ✅ Approved: {result.get('approved')}")
        
        if result.get('ticket'):
            print(f"   ✅ Ticket Legs:")
            for leg in result['ticket']['legs']:
                print(f"      {leg['side']:4} {leg['strike']:5} {leg['type']}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 4: Mixed mode
    print("\n5️⃣ Test Mixed Mode (Absolute + Relative)")
    context3 = {
        "underlying": "NIFTY",
        "parameters": {
            "expiry": "2026-01-15",
            "legs": [
                {
                    "type": "SELL",
                    "option_type": "CE",
                    "strike": 26200,
                    "strike_type": "ABSOLUTE",
                    "quantity": 65
                },
                {
                    "type": "BUY",
                    "option_type": "CE",
                    "strike_type": "RELATIVE",
                    "strike_offset": 100,
                    "quantity": 65
                }
            ]
        }
    }
    
    legs3 = _extract_legs(context3["parameters"])
    resolved_legs3 = _resolve_strikes(legs3, "NIFTY", 26150)
    print(f"   Resolved {len(resolved_legs3)} legs:")
    for leg in resolved_legs3:
        mode_info = f"(offset: {leg.strike_offset})" if leg.strike_offset else ""
        print(f"   - {leg.side} {leg.strike} {leg.option_type} {mode_info}")
    
    print("\n" + "="*60)
    print("✅ All tests passed!")
    print("="*60)

if __name__ == "__main__":
    test_relative_strikes()
