#!/usr/bin/env python3
"""Test Signal Diagnostics endpoint"""
import sqlite3
import httpx
import asyncio
import time

# Check database
print("=" * 70)
print("SIGNAL DIAGNOSTICS CHECK")
print("=" * 70)

db = sqlite3.connect('backend/trading.db')
cursor = db.cursor()

print("\n📊 Database Status:")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='signal_outcomes'")
if not cursor.fetchone():
    print("  ❌ Table signal_outcomes does NOT exist")
    db.close()
else:
    print("  ✅ Table signal_outcomes EXISTS")
    
    # Count records
    cursor.execute('SELECT COUNT(*) FROM signal_outcomes')
    count = cursor.fetchone()[0]
    print(f"  📈 Records: {count}")
    
    if count > 0:
        cursor.execute('SELECT intent_id, underlying, strategy, signal_bias, exit_time FROM signal_outcomes LIMIT 3')
        rows = cursor.fetchall()
        print('  Sample records:')
        for row in rows:
            print(f'    - intent_id: {row[0]}, underlying: {row[1]}, strategy: {row[2]}, bias: {row[3]}, exit_time: {row[4]}')
    
    db.close()

# Test endpoint
print("\n🌐 API Endpoint Test:")
async def test_endpoint():
    async with httpx.AsyncClient(timeout=10, verify=False) as client:
        try:
            response = await client.get(
                "http://127.0.0.1:8000/journal/signal-diagnostics",
                params={
                    "limit": 50,
                    "lookback_days": 30
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                print("  ✅ Endpoint responding (HTTP 200)")
                print(f"  📊 Summary: {data.get('summary', {})}")
                print(f"  📊 By Signal Bias: {list(data.get('by_signal_bias', {}).keys())}")
                print(f"  📊 By Strategy: {list(data.get('by_strategy', {}).keys())}")
                print(f"  📊 By Market Mode: {list(data.get('by_market_mode', {}).keys())}")
                print(f"  📊 By IV Regime: {list(data.get('by_iv_regime', {}).keys())}")
                print(f"  📊 Trades counted: {data.get('count', 0)}")
            else:
                print(f"  ❌ API returned {response.status_code}")
                print(f"     Response: {response.text[:200]}")
        except Exception as e:
            print(f"  ⚠️  Could not connect to API: {e}")
            print(f"     Is the backend running on port 8000?")

print("  Testing API (waiting 1s for server)...")
time.sleep(1)
asyncio.run(test_endpoint())

print("\n" + "=" * 70)
print("✅ Signal Diagnostics Status Report Complete")
print("=" * 70)
