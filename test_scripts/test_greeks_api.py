#!/usr/bin/env python3
"""
Quick test script for Greeks API endpoint
Run this after backend is started to verify the endpoint works
"""

import requests
import json
import sys

API_URL = "http://localhost:8000/greeks/calculate"

# Test payload - Single BUY CALL
test_payload = {
    "legs": [
        {
            "type": "BUY",
            "option_type": "CE",
            "strike": 26000,
            "spot": 26150,
            "expiry_days": 7,
            "volatility": 20.5,
            "quantity": 1
        }
    ],
    "spot": 26150,
    "rate": 5.0
}

print("=" * 60)
print("Testing Greeks API Endpoint")
print("=" * 60)
print(f"\n📍 Endpoint: POST {API_URL}")
print(f"\n📤 Request Payload:")
print(json.dumps(test_payload, indent=2))

try:
    print(f"\n⏳ Sending request...\n")
    response = requests.post(API_URL, json=test_payload)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ SUCCESS!\n")
        data = response.json()
        print("📥 Response:")
        print(json.dumps(data, indent=2))
        
        print("\n📊 Greeks Summary:")
        print(f"  Delta (Δ):  {data['delta']:.4f}  [Directional exposure]")
        print(f"  Gamma (Γ):  {data['gamma']:.6f}  [Delta acceleration]")
        print(f"  Theta (Θ):  {data['theta']:.2f}     [Daily decay]")
        print(f"  Vega (ν):   {data['vega']:.2f}     [IV sensitivity]")
        print(f"  Rho (ρ):    {data['rho']:.2f}     [Rate sensitivity]")
        print(f"  Premium:    {data['premium']:.2f}")
        
    else:
        print(f"❌ ERROR - Status {response.status_code}\n")
        print("Response:")
        print(json.dumps(response.json(), indent=2))
        
except requests.exceptions.ConnectionError:
    print("❌ Connection Error!")
    print("   Make sure backend is running on http://localhost:8000")
    print("   Run: cd backend && python -m uvicorn app.main:app --reload")
    sys.exit(1)
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("Test 2: Multi-leg strategy (Call Spread)")
print("=" * 60)

# Test payload 2 - Call Spread (BUY 26000 CALL, SELL 26200 CALL)
test_payload_2 = {
    "legs": [
        {
            "type": "BUY",
            "option_type": "CE",
            "strike": 26000,
            "spot": 26150,
            "expiry_days": 7,
            "volatility": 20.5,
            "quantity": 1
        },
        {
            "type": "SELL",
            "option_type": "CE",
            "strike": 26200,
            "spot": 26150,
            "expiry_days": 7,
            "volatility": 20.5,
            "quantity": 1
        }
    ],
    "spot": 26150,
    "rate": 5.0
}

print(f"\n📤 Call Spread Payload:")
print(json.dumps(test_payload_2, indent=2))

try:
    print(f"\n⏳ Sending request...\n")
    response = requests.post(API_URL, json=test_payload_2)
    
    if response.status_code == 200:
        print("✅ SUCCESS!\n")
        data = response.json()
        print("📊 Call Spread Greeks:")
        print(f"  Delta (Δ):  {data['delta']:.4f}")
        print(f"  Gamma (Γ):  {data['gamma']:.6f}")
        print(f"  Theta (Θ):  {data['theta']:.2f}")
        print(f"  Vega (ν):   {data['vega']:.2f}")
        print(f"  Rho (ρ):    {data['rho']:.2f}")
        print(f"  Premium:    {data['premium']:.2f}")
        print(f"\n✓ Leg Details:")
        for i, leg in enumerate(data['legs_details'], 1):
            print(f"  Leg {i}: {leg['type']} {leg['option_type']} {leg['strike']}")
            print(f"    Delta: {leg['delta']:.4f}, Gamma: {leg['gamma']:.6f}")
    else:
        print(f"❌ ERROR - Status {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 60)
print("✓ All tests completed!")
print("=" * 60)
