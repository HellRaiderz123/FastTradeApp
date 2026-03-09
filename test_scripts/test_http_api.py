#!/usr/bin/env python3
"""Test the HTTP API endpoint"""
import httpx
import json

print("\n" + "="*80)
print("TESTING HTTP API ENDPOINT")
print("="*80)

try:
    response = httpx.get(
        "http://127.0.0.1:8000/journal/signal-diagnostics",
        params={
            "limit": 200,
            "lookback_days": 30,
        },
        timeout=10
    )
    
    print(f"\nStatus Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        summary = data.get('summary', {})
        print(f"\n✅ API Response received!")
        print(f"\n📊 Summary:")
        print(f"   Trades: {summary.get('trades', 0)}")
        print(f"   Wins: {summary.get('wins', 0)}")
        print(f"   Losses: {summary.get('losses', 0)}")
        print(f"   Win Rate: {summary.get('win_rate_pct', 0)}%")
        print(f"   Net P&L: ₹{summary.get('net_pnl', 0)}")
        print(f"   Profit Factor: {summary.get('profit_factor', 'N/A')}")
        
        print(f"\n📈 By Signal Bias:")
        for key, value in data.get('by_signal_bias', {}).items():
            print(f"   {key}: {value['trades']} trades, {value['win_rate_pct']}% win, ₹{value['net_pnl']} P&L")
        
        print(f"\n📊 By Strategy:")
        for key, value in data.get('by_strategy', {}).items():
            print(f"   {key}: {value['trades']} trades, {value['win_rate_pct']}% win, ₹{value['net_pnl']} P&L")
        
        if summary.get('trades', 0) > 0:
            print("\n✅ SUCCESS! Signal Diagnostics is working in the Journal!")
        else:
            print("\n⚠️ API returned empty results - check logs")
    else:
        print(f"\n❌ HTTP Error {response.status_code}")
        print(f"Response: {response.text}")

except Exception as e:
    print(f"\n⚠️ Could not connect to API: {e}")
    print("   Make sure the backend server is running on http://127.0.0.1:8000")
    print("\n   Start backend with: python -m uvicorn app.main:app --reload")
