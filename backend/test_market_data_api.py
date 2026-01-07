#!/usr/bin/env python3
"""Test market data API endpoints"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000/market"

def test_ltp():
    """Test get LTP endpoint"""
    print("\n" + "="*60)
    print("TEST: GET LTP")
    print("="*60)
    
    url = f"{BASE_URL}/ltp/NIFTY"
    try:
        response = requests.get(url)
        print(f"Status: {response.status_code}")
        data = response.json()
        print(json.dumps(data, indent=2))
        return data
    except Exception as e:
        print(f"Error: {e}")
        return None


def test_expiries():
    """Test get available expiries"""
    print("\n" + "="*60)
    print("TEST: GET EXPIRIES")
    print("="*60)
    
    url = f"{BASE_URL}/expiries/NIFTY"
    try:
        response = requests.get(url)
        print(f"Status: {response.status_code}")
        data = response.json()
        print(json.dumps(data, indent=2))
        return data
    except Exception as e:
        print(f"Error: {e}")
        return None


def test_option_premium():
    """Test get option premium"""
    print("\n" + "="*60)
    print("TEST: GET OPTION PREMIUM")
    print("="*60)
    
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    url = f"{BASE_URL}/option-premium"
    params = {
        "symbol": "NIFTY",
        "strike": 26000,
        "option_type": "CE",
        "expiry": tomorrow
    }
    
    try:
        response = requests.get(url, params=params)
        print(f"Status: {response.status_code}")
        data = response.json()
        print(json.dumps(data, indent=2))
        return data
    except Exception as e:
        print(f"Error: {e}")
        return None


def test_option_chain():
    """Test get option chain"""
    print("\n" + "="*60)
    print("TEST: GET OPTION CHAIN")
    print("="*60)
    
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    url = f"{BASE_URL}/option-chain/NIFTY"
    params = {
        "expiry": tomorrow
    }
    
    try:
        response = requests.get(url, params=params)
        print(f"Status: {response.status_code}")
        data = response.json()
        
        # Print summary instead of full chain
        if "options" in data:
            print(f"Symbol: {data.get('symbol')}")
            print(f"Spot: {data.get('spot')}")
            print(f"Expiry: {data.get('expiry')}")
            print(f"Total options: {len(data.get('options', []))}")
            if data.get('options'):
                print("\nFirst few options:")
                for opt in data.get('options', [])[:3]:
                    print(f"  Strike {opt['strike']}: CE {opt['ce_premium']}, PE {opt['pe_premium']}")
        else:
            print(json.dumps(data, indent=2))
        
        return data
    except Exception as e:
        print(f"Error: {e}")
        return None


def test_integration():
    """Test full integration"""
    print("\n" + "="*60)
    print("INTEGRATION TEST: Full Market Data Flow")
    print("="*60)
    
    # Get spot
    spot_data = test_ltp()
    if not spot_data:
        print("❌ Failed to get spot price")
        return
    
    spot = spot_data.get("ltp", 26150)
    print(f"\n✅ Got spot: {spot}")
    
    # Get expiries
    expiry_data = test_expiries()
    if not expiry_data:
        print("❌ Failed to get expiries")
        return
    
    expiries = expiry_data.get("expiries", [])
    if expiries:
        selected_expiry = expiries[0]
        print(f"✅ Got expiries: {expiries}")
        print(f"   Selected: {selected_expiry}")
    else:
        print("❌ No expiries found")
        return
    
    # Get premium for ATM call
    atm_strike = int(spot / 100) * 100
    premium_data = test_option_premium()
    if premium_data:
        premium = premium_data.get("premium")
        print(f"\n✅ Got premium for {atm_strike} CE: {premium}")
    else:
        print(f"⚠️  Could not fetch premium (may be fallback)")


if __name__ == "__main__":
    print("\n" + "🧪 Market Data API Tests".center(60, "="))
    
    test_ltp()
    test_expiries()
    test_option_premium()
    test_option_chain()
    test_integration()
    
    print("\n" + "="*60)
    print("✅ All tests completed!")
    print("="*60 + "\n")
