#!/usr/bin/env python3
"""Test Expense Forecast functionality"""
import httpx
import asyncio
import json
from datetime import datetime

async def test_expense_forecast():
    async with httpx.AsyncClient(timeout=10, verify=False) as client:
        print("=" * 70)
        print("EXPENSE FORECAST TEST")
        print("=" * 70)
        
        # Test 1: Get current forecasts (should be empty initially)
        print("\n📊 Test 1: Get current forecasts")
        try:
            response = await client.get("http://127.0.0.1:8000/finance/forecast")
            if response.status_code == 200:
                forecasts = response.json()
                print(f"  ✅ Status: {response.status_code}")
                print(f"  📈 Forecasts found: {len(forecasts)}")
                if forecasts:
                    for f in forecasts[:3]:
                        print(f"     - {f['category']}: {f['predicted_amount']:.2f} ({f['confidence']:.0%} confidence)")
            else:
                print(f"  ❌ Status: {response.status_code}")
        except Exception as e:
            print(f"  ⚠️  Error: {e}")
        
        # Test 2: Generate forecast for top categories
        categories = ["Travel", "Food", "Bills"]
        print(f"\n📊 Test 2: Generate forecasts for {categories}")
        for cat in categories:
            try:
                response = await client.post(
                    f"http://127.0.0.1:8000/finance/forecast/{cat}?months_back=3"
                )
                if response.status_code == 200:
                    data = response.json()
                    print(f"  ✅ {cat}: {data.get('predicted_amount', 'N/A'):.2f}")
                else:
                    print(f"  ❌ {cat}: {response.status_code} - {response.text[:100]}")
            except Exception as e:
                print(f"  ⚠️  {cat}: {e}")
        
        # Test 3: Get forecasts again
        print(f"\n📊 Test 3: Get updated forecasts")
        try:
            response = await client.get("http://127.0.0.1:8000/finance/forecast")
            if response.status_code == 200:
                forecasts = response.json()
                print(f"  ✅ Forecasts now: {len(forecasts)}")
                if forecasts:
                    print("\n  📋 Forecast Summary:")
                    for f in forecasts:
                        print(f"     {f['category']:20} {f['predicted_amount']:12.2f}  Conf: {f['confidence']:.0%}")
            else:
                print(f"  ❌ Status: {response.status_code}")
        except Exception as e:
            print(f"  ⚠️  Error: {e}")
        
        print("\n" + "=" * 70)

asyncio.run(test_expense_forecast())
