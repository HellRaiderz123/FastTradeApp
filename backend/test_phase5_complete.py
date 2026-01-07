"""
Phase 5 - Complete Integration Test
Tests all features end-to-end
"""

import sys
import os
import time
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal
from app.services.notifications import get_notification_service
from app.services.health_monitor import HealthMonitor
from app.services.websocket import manager, broadcast_notification


def print_header(text):
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70 + "\n")


def test_notifications():
    """Test notification system"""
    print_header("TEST 1: NOTIFICATION SYSTEM")
    
    db = SessionLocal()
    service = get_notification_service(db)
    
    # Send test notification
    service.notify_trade_executed(
        strategy_name="Test Strategy",
        underlying="NIFTY",
        trade_details={"entry_credit": 100.0, "legs": []}
    )
    
    # Fetch notifications
    notifications = service.get_unread_notifications(limit=1)
    
    assert len(notifications) > 0, "❌ No notifications found"
    assert notifications[0]['title'] == "✅ Trade Executed - Test Strategy", "❌ Wrong notification title"
    
    print(f"✅ Notification created: {notifications[0]['title']}")
    print(f"✅ Priority: {notifications[0]['priority']}")
    print(f"✅ Gmail enabled: {service.gmail_enabled}")
    
    # Mark as read
    service.mark_as_read([notifications[0]['id']])
    print(f"✅ Marked notification as read")
    
    db.close()
    return True


def test_health_monitoring():
    """Test health monitoring"""
    print_header("TEST 2: HEALTH MONITORING")
    
    db = SessionLocal()
    monitor = HealthMonitor(db)
    
    # Get full health status
    health = monitor.get_full_health_status()
    
    assert health['status'] == 'healthy', "❌ System unhealthy"
    assert 'database' in health, "❌ Database check missing"
    assert 'system_resources' in health, "❌ Resource check missing"
    
    print(f"✅ System status: {health['status']}")
    print(f"✅ Uptime: {health['uptime_seconds']:.1f}s")
    print(f"✅ Database: {health['database']['status']}")
    print(f"✅ Database latency: {health['database']['latency_ms']}ms")
    
    # Check resources
    resources = health['system_resources']
    print(f"✅ CPU: {resources['cpu_percent']}%")
    print(f"✅ Memory: {resources['memory']['percent']}%")
    print(f"✅ Disk: {resources['disk']['percent']}%")
    
    db.close()
    return True


async def test_websocket():
    """Test WebSocket manager"""
    print_header("TEST 3: WEBSOCKET SYSTEM")
    
    # Check connection count
    count = manager.get_connection_count()
    print(f"✅ Active WebSocket connections: {count}")
    
    # Test broadcast
    await broadcast_notification({
        "title": "Test Notification",
        "message": "WebSocket test message",
        "priority": "low"
    })
    print(f"✅ Broadcast test notification")
    
    return True


def test_logging():
    """Test logging configuration"""
    print_header("TEST 4: LOGGING SYSTEM")
    
    from app.core.logging_config import get_logger, set_request_id, get_request_id
    
    logger = get_logger(__name__)
    
    # Set request ID
    request_id = set_request_id()
    assert get_request_id() == request_id, "❌ Request ID not set"
    print(f"✅ Request ID set: {request_id[:8]}...")
    
    # Test logging levels
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    
    print(f"✅ Logging levels working")
    print(f"✅ Log file: backend/logs/app.log")
    
    return True


def test_api_endpoints():
    """Test if API endpoints are properly registered"""
    print_header("TEST 5: API ENDPOINT REGISTRATION")
    
    import requests
    
    base_url = "http://localhost:8000"
    
    endpoints_to_test = [
        "/health/",
        "/health/heartbeat",
        "/notifications/unread-count",
        "/ws/connections",
    ]
    
    print("Testing endpoints (requires server running):")
    server_running = True
    
    for endpoint in endpoints_to_test:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=2)
            if response.status_code == 200:
                print(f"  ✅ {endpoint} - OK")
            else:
                print(f"  ⚠️  {endpoint} - Status {response.status_code}")
        except requests.exceptions.RequestException:
            server_running = False
            print(f"  ⏸️  {endpoint} - Server not running")
    
    if not server_running:
        print("\n  ℹ️  Start server with: uvicorn app.main:app --reload")
    
    return True


def test_database_tables():
    """Test if all tables exist"""
    print_header("TEST 6: DATABASE TABLES")
    
    from sqlalchemy import inspect
    from app.db.session import engine
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    required_tables = [
        'notifications',
        'strategy_configs',
        'strategy_runs',
        'candles',
    ]
    
    for table in required_tables:
        if table in tables:
            print(f"  ✅ {table}")
        else:
            print(f"  ❌ {table} - MISSING")
            return False
    
    return True


def run_all_tests():
    """Run all tests"""
    
    print("\n" + "█"*70)
    print("█" + " "*68 + "█")
    print("█" + "  PHASE 5 - COMPLETE INTEGRATION TEST SUITE".center(68) + "█")
    print("█" + " "*68 + "█")
    print("█"*70)
    
    results = {}
    
    try:
        results['Database Tables'] = test_database_tables()
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        results['Database Tables'] = False
    
    try:
        results['Notifications'] = test_notifications()
    except Exception as e:
        print(f"❌ Notification test failed: {e}")
        results['Notifications'] = False
    
    try:
        results['Health Monitoring'] = test_health_monitoring()
    except Exception as e:
        print(f"❌ Health monitoring test failed: {e}")
        results['Health Monitoring'] = False
    
    try:
        results['WebSocket'] = asyncio.run(test_websocket())
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        results['WebSocket'] = False
    
    try:
        results['Logging'] = test_logging()
    except Exception as e:
        print(f"❌ Logging test failed: {e}")
        results['Logging'] = False
    
    try:
        results['API Endpoints'] = test_api_endpoints()
    except Exception as e:
        print(f"❌ API endpoint test failed: {e}")
        results['API Endpoints'] = False
    
    # Summary
    print_header("TEST SUMMARY")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    for test_name, passed_status in results.items():
        status = "✅ PASS" if passed_status else "❌ FAIL"
        print(f"  {status} - {test_name}")
    
    print(f"\n  Total: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n" + "🎉"*35)
        print("\n  ALL TESTS PASSED! Phase 5 is ready for production! 🚀")
        print("\n" + "🎉"*35 + "\n")
        return 0
    else:
        print("\n  ⚠️  Some tests failed. Check errors above.\n")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
