#!/usr/bin/env python3
"""Test Expense Forecast functionality"""
import requests

print("=" * 70)
print("EXPENSE FORECAST TEST")
print("=" * 70)

# Test 1: Get current forecasts
print("\n📊 Test 1: Get current forecasts")
try:
    response = requests.get("http://127.0.0.1:8000/finance/forecast", timeout=5)
    if response.status_code == 200:
        forecasts = response.json()
        print(f"  ✅ Status: {response.status_code}")
        print(f"  📈 Forecasts found: {len(forecasts)}")
    else:
        print(f"  ❌ Status: {response.status_code}")
except Exception as e:
    print(f"  ⚠️  Error: {e}")

# Test 2: Generate forecasts
print("\n📊 Test 2: Generate forecasts")
categories = ["Travel", "Food", "Bills"]
for cat in categories:
    try:
        response = requests.post(
            f"http://127.0.0.1:8000/finance/forecast/{cat}?months_back=3", 
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            predicted = data.get("predicted_amount", "N/A")
            print(f"  ✅ {cat}: {predicted:.2f}" if isinstance(predicted, (int, float)) else f"  ✅ {cat}: {predicted}")
        else:
            print(f"  ⚠️  {cat}: {response.status_code}")
    except Exception as e:
        print(f"  ⚠️  {cat}: {e}")

# Test 3: Get forecasts again
print("\n📊 Test 3: Get updated forecasts")
try:
    response = requests.get("http://127.0.0.1:8000/finance/forecast", timeout=5)
    if response.status_code == 200:
        forecasts = response.json()
        print(f"  ✅ Forecasts: {len(forecasts)}")
        if forecasts:
            print("\n  Category forecasts:")
            for f in forecasts[:5]:
                cat = f.get("category", "N/A")
                amt = f.get("predicted_amount", 0)
                conf = f.get("confidence", 0)
                print(f"    {cat:20} ₹{amt:10.2f}  Confidence: {conf:.0%}")
    else:
        print(f"  ❌ Status: {response.status_code}")
except Exception as e:
    print(f"  ⚠️  Error: {e}")

print("\n" + "=" * 70)
