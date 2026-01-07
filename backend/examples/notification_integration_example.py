"""
Example integration: Notify on trade execution
"""

from app.services.notifications import get_notification_service
from app.db.session import SessionLocal

# After successful trade execution
def execute_trade_with_notification():
    db = SessionLocal()
    
    try:
        # ... your trade execution logic ...
        
        # Send notification
        notification_service = get_notification_service(db)
        notification_service.notify_trade_executed(
            strategy_name="NIFTY Bull Put",
            underlying="NIFTY",
            trade_details={
                "entry_credit": 500.50,
                "legs": [
                    {"strike": 26000, "type": "PE", "side": "SELL"},
                    {"strike": 25900, "type": "PE", "side": "BUY"}
                ]
            }
        )
        
    finally:
        db.close()


# On exit with profit
def exit_trade_with_notification(pnl: float, pnl_pct: float, exit_reason: str):
    db = SessionLocal()
    
    try:
        notification_service = get_notification_service(db)
        
        if exit_reason == "TP":
            notification_service.notify_tp_hit("NIFTY Bull Put", pnl, pnl_pct)
        elif exit_reason == "SL":
            notification_service.notify_sl_hit("NIFTY Bull Put", pnl, pnl_pct)
        elif exit_reason == "TRAILING_SL":
            notification_service.notify_trailing_sl_hit("NIFTY Bull Put", pnl, pnl_pct)
        
    finally:
        db.close()


# On system error
def handle_error_with_notification(error: Exception, component: str):
    db = SessionLocal()
    
    try:
        notification_service = get_notification_service(db)
        notification_service.notify_system_error(
            error_type=type(error).__name__,
            error_message=str(error),
            component=component,
            stack_trace=None  # or traceback.format_exc()
        )
        
    finally:
        db.close()


# Check and notify P&L threshold
def check_pnl_threshold(daily_pnl: float, capital: float):
    """Check if daily P&L crossed ±5% threshold"""
    db = SessionLocal()
    
    try:
        pnl_pct = (daily_pnl / capital) * 100
        
        if abs(pnl_pct) >= 5.0:
            notification_service = get_notification_service(db)
            notification_service.notify_pnl_threshold(
                daily_pnl=daily_pnl,
                daily_pnl_pct=pnl_pct,
                capital=capital,
                threshold_type="profit" if pnl_pct > 0 else "loss"
            )
        
    finally:
        db.close()
