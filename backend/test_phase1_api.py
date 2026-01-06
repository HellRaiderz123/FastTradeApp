"""
API Test: Verify strategy CRUD endpoints
"""

import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def test_create_strategy():
    """Test POST /strategies"""
    print("\n📝 Testing CREATE strategy...")
    
    payload = {
        "name": "NIFTY_Conservative",
        "description": "Conservative spread on NIFTY",
        "strategy_type": "option_spread_15m",
        "underlying": "NIFTY",
        "parameters": {
            "risk_mode": "BALANCED",
            "lots": 1,
            "capital": 100000
        }
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/strategies", json=payload, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Created strategy ID: {data['id']} - {data['name']}")
            return data['id']
        else:
            print(f"❌ Failed: {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def test_list_strategies():
    """Test GET /strategies"""
    print("\n📋 Testing LIST strategies...")
    
    try:
        resp = requests.get(f"{BASE_URL}/strategies", timeout=5)
        if resp.status_code == 200:
            strategies = resp.json()
            print(f"✅ Found {len(strategies)} strategies")
            for s in strategies:
                print(f"   - {s['name']} ({s['underlying']}) - Enabled: {s['enabled']}")
            return True
        else:
            print(f"❌ Failed: {resp.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_enable_strategy(strategy_id):
    """Test POST /strategies/{id}/enable"""
    print(f"\n🚀 Testing ENABLE strategy {strategy_id}...")
    
    try:
        resp = requests.post(f"{BASE_URL}/strategies/{strategy_id}/enable", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Enabled strategy: {data['strategy']['name']}")
            return True
        else:
            print(f"❌ Failed: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_get_status(strategy_id):
    """Test GET /strategies/{id}/status"""
    print(f"\n⚙️ Testing GET status for {strategy_id}...")
    
    try:
        resp = requests.get(f"{BASE_URL}/strategies/{strategy_id}/status", timeout=5)
        if resp.status_code == 200:
            status = resp.json()
            print(f"✅ Status: {status['name']}")
            print(f"   - Enabled: {status['enabled']}")
            print(f"   - Deployed at: {status['deployed_at']}")
            return True
        else:
            print(f"❌ Failed: {resp.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_disable_strategy(strategy_id):
    """Test POST /strategies/{id}/disable"""
    print(f"\n⛔ Testing DISABLE strategy {strategy_id}...")
    
    try:
        resp = requests.post(f"{BASE_URL}/strategies/{strategy_id}/disable", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Disabled strategy: {data['strategy']['name']}")
            return True
        else:
            print(f"❌ Failed: {resp.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_delete_strategy(strategy_id):
    """Test DELETE /strategies/{id}"""
    print(f"\n🗑️ Testing DELETE strategy {strategy_id}...")
    
    try:
        resp = requests.delete(f"{BASE_URL}/strategies/{strategy_id}", timeout=5)
        if resp.status_code == 200:
            print(f"✅ Deleted strategy")
            return True
        else:
            print(f"❌ Failed: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("PHASE 1 API TEST - Strategy Management")
    print("=" * 60)
    print("⏳ Waiting for server to be ready...")
    time.sleep(1)
    
    # Test workflow
    strategy_id = test_create_strategy()
    
    if strategy_id:
        test_list_strategies()
        test_get_status(strategy_id)
        test_enable_strategy(strategy_id)
        test_get_status(strategy_id)
        test_disable_strategy(strategy_id)
        test_delete_strategy(strategy_id)
        
        print("\n" + "=" * 60)
        print("✅ ALL API TESTS COMPLETED")
        print("=" * 60)
    else:
        print("❌ Could not create strategy, skipping tests")
