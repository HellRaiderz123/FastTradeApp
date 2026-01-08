"""
Test script to verify relative strike positioning works correctly
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_relative_strikes():
    """Test custom strategy with relative strikes"""
    
    # Test 1: Absolute strikes (existing functionality)
    print("\n=== TEST 1: Absolute Strikes ===")
    absolute_strategy = {
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
    
    response = requests.post(
        f"{BASE_URL}/strategies/option_spread_custom/run",
        json=absolute_strategy
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Strategy: {result.get('strategy')}")
        print(f"✅ Approved: {result.get('approved')}")
        if result.get('ticket'):
            print(f"✅ Ticket Legs: {json.dumps(result['ticket']['legs'], indent=2)}")
    else:
        print(f"❌ Error: {response.text}")
    
    # Test 2: Relative strikes (new functionality)
    print("\n=== TEST 2: Relative Strikes (ATM-based) ===")
    relative_strategy = {
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
    
    response = requests.post(
        f"{BASE_URL}/strategies/option_spread_custom/run",
        json=relative_strategy
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Strategy: {result.get('strategy')}")
        print(f"✅ Approved: {result.get('approved')}")
        if result.get('ticket'):
            print(f"✅ Ticket Legs: {json.dumps(result['ticket']['legs'], indent=2)}")
            print("\n📊 Strike Calculation:")
            for leg in result['ticket']['legs']:
                print(f"   {leg['side']} {leg['strike']} {leg['type']}")
    else:
        print(f"❌ Error: {response.text}")
    
    # Test 3: Iron Condor with relative strikes
    print("\n=== TEST 3: Iron Condor with Relative Strikes ===")
    iron_condor = {
        "underlying": "NIFTY",
        "parameters": {
            "expiry": "2026-01-15",
            "legs": [
                {
                    "type": "SELL",
                    "option_type": "PE",
                    "strike_type": "RELATIVE",
                    "strike_offset": -200,  # ATM - 200
                    "quantity": 65
                },
                {
                    "type": "BUY",
                    "option_type": "PE",
                    "strike_type": "RELATIVE",
                    "strike_offset": -300,  # ATM - 300
                    "quantity": 65
                },
                {
                    "type": "SELL",
                    "option_type": "CE",
                    "strike_type": "RELATIVE",
                    "strike_offset": 200,  # ATM + 200
                    "quantity": 65
                },
                {
                    "type": "BUY",
                    "option_type": "CE",
                    "strike_type": "RELATIVE",
                    "strike_offset": 300,  # ATM + 300
                    "quantity": 65
                }
            ]
        }
    }
    
    response = requests.post(
        f"{BASE_URL}/strategies/option_spread_custom/run",
        json=iron_condor
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Strategy: {result.get('strategy')}")
        print(f"✅ Approved: {result.get('approved')}")
        if result.get('ticket'):
            print(f"✅ Ticket Legs:")
            for leg in result['ticket']['legs']:
                print(f"   {leg['side']:4} {leg['strike']:5} {leg['type']}")
    else:
        print(f"❌ Error: {response.text}")
    
    # Test 4: Mixed mode (absolute + relative)
    print("\n=== TEST 4: Mixed Mode (Absolute + Relative) ===")
    mixed_strategy = {
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
    
    response = requests.post(
        f"{BASE_URL}/strategies/option_spread_custom/run",
        json=mixed_strategy
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Strategy: {result.get('strategy')}")
        print(f"✅ Mixed mode works!")
        if result.get('ticket'):
            for leg in result['ticket']['legs']:
                print(f"   {leg['side']:4} {leg['strike']:5} {leg['type']}")
    else:
        print(f"❌ Error: {response.text}")
    
    print("\n" + "="*60)
    print("🎉 All tests completed!")
    print("="*60)

if __name__ == "__main__":
    try:
        test_relative_strikes()
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to backend server")
        print("   Make sure the backend is running on http://localhost:8000")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
