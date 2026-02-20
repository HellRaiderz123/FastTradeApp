"""
Phase 2 API Test: Test execution endpoints
"""

import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def test_create_test_strategies():
    """Create test strategies"""
    print("\n📝 Creating test strategies...")
    
    strategies = [
        {
            "name": "NIFTY_15m_Test",
            "description": "Test strategy for NIFTY",
            "strategy_type": "option_spread_15m",
            "underlying": "NIFTY",
            "parameters": {"risk_mode": "CONSERVATIVE", "lots": 1}
        },
        {
            "name": "BANKNIFTY_15m_Test",
            "description": "Test strategy for BANKNIFTY",
            "strategy_type": "option_spread_15m",
            "underlying": "BANKNIFTY",
            "parameters": {"risk_mode": "BALANCED", "lots": 1}
        },
    ]
    
    created_ids = []
    for strat in strategies:
        try:
            resp = requests.post(f"{BASE_URL}/strategies", json=strat, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                created_ids.append(data['id'])
                print(f"   ✅ Created: {data['name']} (ID: {data['id']})")
            else:
                print(f"   ❌ Failed: {resp.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    return created_ids


def test_execute_single(strategy_id):
    """Test single strategy execution"""
    print(f"\n🚀 Testing single strategy execution (ID: {strategy_id})...")
    
    payload = {
        "strategy_id": strategy_id,
        "additional_context": {"test_mode": True}
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/strategies/run/single", json=payload, timeout=10)
        if resp.status_code == 200:
            result = resp.json()
            print(f"   ✅ Execution successful")
            print(f"      - Strategy: {result.get('strategy_name')}")
            print(f"      - Executed At: {result.get('executed_at')}")
            return True
        else:
            print(f"   ❌ Failed: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_execute_multiple(strategy_ids):
    """Test multiple strategy execution"""
    print(f"\n⚡ Testing multiple strategy execution (IDs: {strategy_ids})...")
    
    payload = {
        "strategy_ids": strategy_ids,
        "additional_context": {"test_mode": True}
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/strategies/run/multiple", json=payload, timeout=15)
        if resp.status_code == 200:
            result = resp.json()
            print(f"   ✅ Multi-execution completed")
            print(f"      - Total: {result.get('total')}")
            print(f"      - Completed: {result.get('completed')}")
            print(f"      - Failed: {result.get('failed')}")
            return True
        else:
            print(f"   ❌ Failed: {resp.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_execute_all():
    """Test execute all enabled"""
    print(f"\n🌟 Testing execute all enabled strategies...")
    
    payload = {
        "additional_context": {"test_mode": True}
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/strategies/run/all", json=payload, timeout=15)
        if resp.status_code == 200:
            result = resp.json()
            print(f"   ✅ All execution completed")
            print(f"      - Total: {result.get('total')}")
            print(f"      - Completed: {result.get('completed')}")
            print(f"      - Failed: {result.get('failed')}")
            return True
        else:
            print(f"   ❌ Failed: {resp.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_get_status(strategy_id):
    """Test get status endpoint"""
    print(f"\n📊 Testing get status (ID: {strategy_id})...")
    
    try:
        resp = requests.get(f"{BASE_URL}/strategies/run/{strategy_id}/status", timeout=5)
        if resp.status_code == 200:
            result = resp.json()
            print(f"   ✅ Status retrieved")
            print(f"      - Name: {result.get('name')}")
            print(f"      - Enabled: {result.get('enabled')}")
            print(f"      - Ready: {result.get('ready')}")
            return True
        else:
            print(f"   ❌ Failed: {resp.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("PHASE 2 - API ENDPOINT TESTING")
    print("=" * 70)
    print("⏳ Waiting for server...")
    time.sleep(1)
    
    # Create test strategies
    strategy_ids = test_create_test_strategies()
    
    if strategy_ids:
        # Test single execution
        test_execute_single(strategy_ids[0])
        
        # Test multiple execution
        test_execute_multiple(strategy_ids)
        
        # Test status
        test_get_status(strategy_ids[0])
        
        # Test execute all
        test_execute_all()
        
        print("\n" + "=" * 70)
        print("✅ PHASE 2 API TESTS COMPLETE")
        print("=" * 70)
    else:
        print("❌ Could not create test strategies")
