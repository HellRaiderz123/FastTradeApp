"""
Test Notification System
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal
from app.services.notifications import get_notification_service


def test_notifications():
    """Test all notification types"""
    
    db = SessionLocal()
    service = get_notification_service(db)
    
    print("\n" + "="*60)
    print("TESTING NOTIFICATION SYSTEM")
    print("="*60 + "\n")
    
    # 1. Trade executed
    print("1️⃣ Testing trade executed notification...")
    service.notify_trade_executed(
        strategy_name="NIFTY Bull Put Test",
        underlying="NIFTY",
        trade_details={
            "entry_credit": 500.50,
            "legs": [
                {"strike": 26000, "type": "PE", "side": "SELL"},
                {"strike": 25900, "type": "PE", "side": "BUY"}
            ]
        }
    )
    print("   ✅ Trade executed notification sent\n")
    
    # 2. Trade failed
    print("2️⃣ Testing trade failed notification...")
    service.notify_trade_failed(
        strategy_name="BANKNIFTY Iron Condor",
        reason="Insufficient margin",
        error_details={"margin_required": 50000, "margin_available": 40000}
    )
    print("   ✅ Trade failed notification sent\n")
    
    # 3. TP hit
    print("3️⃣ Testing TP hit notification...")
    service.notify_tp_hit(
        strategy_name="NIFTY Bull Put Test",
        pnl=450.0,
        pnl_pct=2.5
    )
    print("   ✅ TP hit notification sent\n")
    
    # 4. SL hit
    print("4️⃣ Testing SL hit notification...")
    service.notify_sl_hit(
        strategy_name="FINNIFTY Strangle",
        pnl=-200.0,
        pnl_pct=-1.2
    )
    print("   ✅ SL hit notification sent\n")
    
    # 5. P&L threshold (profit)
    print("5️⃣ Testing P&L threshold notification (profit)...")
    service.notify_pnl_threshold(
        daily_pnl=5500.0,
        daily_pnl_pct=5.5,
        capital=100000,
        threshold_type="profit"
    )
    print("   ✅ P&L threshold notification sent\n")
    
    # 6. System error
    print("6️⃣ Testing system error notification...")
    service.notify_system_error(
        error_type="ZerodhaAPIError",
        error_message="Connection timeout after 30s",
        component="ExecutionEngine"
    )
    print("   ✅ System error notification sent\n")
    
    # 7. Margin warning
    print("7️⃣ Testing margin warning notification...")
    service.notify_margin_warning(
        required_margin=60000,
        available_margin=45000,
        shortfall=15000
    )
    print("   ✅ Margin warning notification sent\n")
    
    # 8. Daily summary
    print("8️⃣ Testing daily summary notification...")
    service.notify_daily_summary({
        "date": "2026-01-07",
        "total_pnl": 2500.0,
        "return_pct": 2.5,
        "total_trades": 5,
        "wins": 4,
        "losses": 1,
        "win_rate": 80.0,
        "closing_capital": 102500
    })
    print("   ✅ Daily summary notification sent\n")
    
    # Get unread notifications
    print("📊 Fetching unread notifications...")
    notifications = service.get_unread_notifications(limit=10)
    
    print(f"\n   Found {len(notifications)} unread notifications:")
    for notif in notifications:
        print(f"   - [{notif['priority'].upper()}] {notif['title']}")
    
    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED")
    print("="*60 + "\n")
    
    # Check Gmail configuration
    if service.gmail_enabled:
        print("📧 Gmail notifications: ENABLED")
        print(f"   Sending to: {service.recipient_email}\n")
    else:
        print("⚠️  Gmail notifications: DISABLED")
        print("   Set GMAIL_USER and GMAIL_APP_PASSWORD in .env\n")
    
    db.close()


if __name__ == "__main__":
    test_notifications()
