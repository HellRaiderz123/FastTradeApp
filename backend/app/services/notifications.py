"""
Notification Service - Multi-channel alerts system
Supports: In-App Notifications + Gmail
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum
import os
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Notification types"""
    TRADE_EXECUTED = "trade_executed"
    TRADE_FAILED = "trade_failed"
    TP_HIT = "tp_hit"
    SL_HIT = "sl_hit"
    TRAILING_SL_HIT = "trailing_sl_hit"
    PNL_THRESHOLD = "pnl_threshold"
    DAILY_SUMMARY = "daily_summary"
    SYSTEM_ERROR = "system_error"
    MARGIN_WARNING = "margin_warning"
    STRATEGY_ENABLED = "strategy_enabled"
    STRATEGY_DISABLED = "strategy_disabled"
    ALERT_TRIGGERED = "alert_triggered"


class NotificationPriority(str, Enum):
    """Priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationService:
    """
    Unified notification service for all alerts
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.gmail_enabled = self._check_gmail_config()
        
        # Load Gmail credentials
        # Primary envs
        gmail_user_env = os.getenv("GMAIL_USER")
        gmail_pass_env = os.getenv("GMAIL_APP_PASSWORD")
        alert_email_env = os.getenv("ALERT_EMAIL")

        # Fallbacks for compatibility with other apps
        from_email_fallback = os.getenv("ALERT_FROM_EMAIL")
        from_password_fallback = os.getenv("ALERT_FROM_PASSWORD")
        to_emails_fallback = os.getenv("ALERT_TO_EMAILS")

        # Derive values
        self.gmail_user = (gmail_user_env or from_email_fallback or "").strip()
        self.gmail_password = (gmail_pass_env or from_password_fallback or "").strip()  # Use app-specific password

        # Choose alert recipient: ALERT_EMAIL > ALERT_TO_EMAILS (first) > gmail_user
        if alert_email_env:
            alert_email_val = alert_email_env
        elif to_emails_fallback:
            alert_email_val = to_emails_fallback.split(",")[0]
        else:
            alert_email_val = self.gmail_user
        self.recipient_email = (alert_email_val or "").strip()
        
        if self.gmail_enabled:
            logger.info("✅ Gmail notifications enabled")
        else:
            logger.warning("⚠️ Gmail notifications disabled - missing credentials")
    
    def _check_gmail_config(self) -> bool:
        """Check if Gmail is properly configured and enabled"""
        creds_ok = bool(
            os.getenv("GMAIL_USER") and 
            os.getenv("GMAIL_APP_PASSWORD")
        )
        enabled_flag = os.getenv("NOTIFY_GMAIL_ENABLED", "true").lower() in ["1", "true", "yes"]
        return creds_ok and enabled_flag
    
    # ============================
    # TRADE NOTIFICATIONS
    # ============================
    
    def notify_trade_executed(
        self, 
        strategy_name: str, 
        underlying: str,
        trade_details: Dict[str, Any]
    ):
        """Notify successful trade execution"""
        message = f"""
        ✅ Trade Executed Successfully
        
        Strategy: {strategy_name}
        Underlying: {underlying}
        Entry Credit: ₹{trade_details.get('entry_credit', 0):,.2f}
        Legs: {len(trade_details.get('legs', []))}
        Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        self._send_notification(
            type=NotificationType.TRADE_EXECUTED,
            title=f"✅ Trade Executed - {strategy_name}",
            message=message.strip(),
            priority=NotificationPriority.MEDIUM,
            metadata=trade_details
        )
    
    def notify_trade_failed(
        self, 
        strategy_name: str, 
        reason: str,
        error_details: Optional[Dict] = None
    ):
        """Notify failed trade execution"""
        message = f"""
        ❌ Trade Execution Failed
        
        Strategy: {strategy_name}
        Reason: {reason}
        Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        Please check logs for details.
        """
        
        self._send_notification(
            type=NotificationType.TRADE_FAILED,
            title=f"❌ Trade Failed - {strategy_name}",
            message=message.strip(),
            priority=NotificationPriority.HIGH,
            metadata=error_details or {}
        )
    
    # ============================
    # EXIT NOTIFICATIONS
    # ============================
    
    def notify_tp_hit(
        self, 
        strategy_name: str, 
        pnl: float,
        pnl_pct: float
    ):
        """Notify take profit hit"""
        message = f"""
        🎯 Take Profit Hit!
        
        Strategy: {strategy_name}
        P&L: ₹{pnl:,.2f}
        Return: {pnl_pct:.2f}%
        Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        Position closed successfully.
        """
        
        self._send_notification(
            type=NotificationType.TP_HIT,
            title=f"🎯 TP Hit - {strategy_name} (+{pnl_pct:.1f}%)",
            message=message.strip(),
            priority=NotificationPriority.MEDIUM,
            metadata={"pnl": pnl, "pnl_pct": pnl_pct}
        )
    
    def notify_sl_hit(
        self, 
        strategy_name: str, 
        pnl: float,
        pnl_pct: float
    ):
        """Notify stop loss hit"""
        message = f"""
        🛑 Stop Loss Hit
        
        Strategy: {strategy_name}
        P&L: ₹{pnl:,.2f}
        Loss: {pnl_pct:.2f}%
        Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        Position closed to limit losses.
        """
        
        self._send_notification(
            type=NotificationType.SL_HIT,
            title=f"🛑 SL Hit - {strategy_name} ({pnl_pct:.1f}%)",
            message=message.strip(),
            priority=NotificationPriority.HIGH,
            metadata={"pnl": pnl, "pnl_pct": pnl_pct}
        )
    
    def notify_trailing_sl_hit(
        self, 
        strategy_name: str, 
        pnl: float,
        pnl_pct: float
    ):
        """Notify trailing stop loss hit"""
        message = f"""
        📈 Trailing Stop Loss Hit
        
        Strategy: {strategy_name}
        Profit Locked: ₹{pnl:,.2f}
        Return: {pnl_pct:.2f}%
        Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        Position closed with profit protection.
        """
        
        self._send_notification(
            type=NotificationType.TRAILING_SL_HIT,
            title=f"📈 Trailing SL - {strategy_name} (+{pnl_pct:.1f}%)",
            message=message.strip(),
            priority=NotificationPriority.MEDIUM,
            metadata={"pnl": pnl, "pnl_pct": pnl_pct}
        )
    
    # ============================
    # P&L NOTIFICATIONS
    # ============================
    
    def notify_pnl_threshold(
        self, 
        daily_pnl: float,
        daily_pnl_pct: float,
        capital: float,
        threshold_type: str  # "profit" or "loss"
    ):
        """Notify when daily P&L crosses threshold (±5%)"""
        emoji = "🎉" if threshold_type == "profit" else "⚠️"
        
        message = f"""
        {emoji} Daily P&L Threshold Crossed
        
        Today's P&L: ₹{daily_pnl:,.2f}
        Return: {daily_pnl_pct:+.2f}%
        Capital: ₹{capital:,.2f}
        
        {'Excellent performance today!' if threshold_type == 'profit' else 'Consider reviewing open positions.'}
        """
        
        self._send_notification(
            type=NotificationType.PNL_THRESHOLD,
            title=f"{emoji} Daily P&L {abs(daily_pnl_pct):.1f}%",
            message=message.strip(),
            priority=NotificationPriority.HIGH,
            metadata={
                "daily_pnl": daily_pnl,
                "daily_pnl_pct": daily_pnl_pct,
                "threshold_type": threshold_type
            }
        )
    
    def notify_daily_summary(
        self, 
        summary: Dict[str, Any]
    ):
        """Send daily trading summary"""
        message = f"""
        📊 Daily Trading Summary - {summary.get('date', 'Today')}
        
        Total P&L: ₹{summary.get('total_pnl', 0):,.2f}
        Return: {summary.get('return_pct', 0):+.2f}%
        
        Trades: {summary.get('total_trades', 0)}
        Wins: {summary.get('wins', 0)} | Losses: {summary.get('losses', 0)}
        Win Rate: {summary.get('win_rate', 0):.1f}%
        
        Closing Capital: ₹{summary.get('closing_capital', 0):,.2f}
        """
        
        self._send_notification(
            type=NotificationType.DAILY_SUMMARY,
            title=f"📊 Daily Summary - {summary.get('date', 'Today')}",
            message=message.strip(),
            priority=NotificationPriority.LOW,
            metadata=summary
        )
    
    # ============================
    # SYSTEM NOTIFICATIONS
    # ============================
    
    def notify_system_error(
        self, 
        error_type: str,
        error_message: str,
        component: str,
        stack_trace: Optional[str] = None
    ):
        """Notify critical system errors"""
        message = f"""
        🚨 SYSTEM ERROR
        
        Component: {component}
        Error Type: {error_type}
        Message: {error_message}
        Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        IMMEDIATE ATTENTION REQUIRED
        """
        
        self._send_notification(
            type=NotificationType.SYSTEM_ERROR,
            title=f"🚨 System Error - {component}",
            message=message.strip(),
            priority=NotificationPriority.CRITICAL,
            metadata={
                "error_type": error_type,
                "component": component,
                "stack_trace": stack_trace
            }
        )
    
    def notify_margin_warning(
        self, 
        required_margin: float,
        available_margin: float,
        shortfall: float
    ):
        """Notify insufficient margin"""
        message = f"""
        ⚠️ MARGIN WARNING
        
        Required: ₹{required_margin:,.2f}
        Available: ₹{available_margin:,.2f}
        Shortfall: ₹{shortfall:,.2f}
        
        Trade blocked to prevent margin call.
        Please add funds or close positions.
        """
        
        self._send_notification(
            type=NotificationType.MARGIN_WARNING,
            title=f"⚠️ Insufficient Margin (₹{shortfall:,.0f} short)",
            message=message.strip(),
            priority=NotificationPriority.CRITICAL,
            metadata={
                "required": required_margin,
                "available": available_margin,
                "shortfall": shortfall
            }
        )
    
    def notify_strategy_status(
        self, 
        strategy_name: str,
        enabled: bool
    ):
        """Notify strategy enable/disable"""
        status = "Enabled" if enabled else "Disabled"
        emoji = "✅" if enabled else "⏸️"
        
        message = f"""
        {emoji} Strategy {status}
        
        Strategy: {strategy_name}
        Status: {status}
        Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        notification_type = NotificationType.STRATEGY_ENABLED if enabled else NotificationType.STRATEGY_DISABLED
        
        self._send_notification(
            type=notification_type,
            title=f"{emoji} {strategy_name} - {status}",
            message=message.strip(),
            priority=NotificationPriority.LOW,
            metadata={"strategy": strategy_name, "enabled": enabled}
        )

    # ============================
    # ALERT NOTIFICATIONS
    # ============================

    def notify_alert_triggered(
        self,
        ticker: str,
        operator: str,
        target_price: float,
        current_price: float,
        alert_id: int
    ):
        """Notify when a price alert is triggered"""
        message = f"""
        🔔 Price Alert Triggered

        Symbol: {ticker}
        Condition: {operator} {target_price}
        Current: {current_price}
        Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """

        self._send_notification(
            type=NotificationType.ALERT_TRIGGERED,
            title=f"🔔 Price Alert - {ticker}",
            message=message.strip(),
            priority=NotificationPriority.HIGH,
            metadata={
                "ticker": ticker,
                "operator": operator,
                "target": target_price,
                "current": current_price,
                "alert_id": alert_id,
            }
        )
    
    # ============================
    # CORE NOTIFICATION LOGIC
    # ============================
    
    def _send_notification(
        self,
        type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority,
        metadata: Dict[str, Any]
    ):
        """Send notification through all enabled channels"""
        
        try:
            # 1. Store in-app notification
            self._store_in_app_notification(type, title, message, priority, metadata)
            
            # 2. Send email for high/critical priority
            if priority in [NotificationPriority.HIGH, NotificationPriority.CRITICAL]:
                if self.gmail_enabled:
                    self._send_email(title, message)
                else:
                    logger.warning(f"Gmail not configured, skipping email for: {title}")
            
            logger.info(f"✅ Notification sent: {title}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send notification: {e}", exc_info=True)
    
    def _store_in_app_notification(
        self,
        type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority,
        metadata: Dict[str, Any]
    ):
        """Store notification in database for in-app display"""
        from app.db.models_notification import Notification
        from app.core.utils.time import now_ist
        
        try:
            notification = Notification(
                type=type.value,
                title=title,
                message=message,
                priority=priority.value,
                data=metadata,
                read=False,
                created_at=now_ist()
            )
            
            self.db.add(notification)
            self.db.commit()
            
            logger.debug(f"Stored in-app notification: {title}")
            
        except Exception as e:
            logger.error(f"Failed to store in-app notification: {e}")
            self.db.rollback()
    
    def _send_email(self, subject: str, body: str):
        """Send email via Gmail SMTP"""
        if not self.gmail_enabled:
            return
        
        try:
            server_host = (os.getenv("SMTP_SERVER", "smtp.gmail.com") or "smtp.gmail.com").strip()
            server_port = int((os.getenv("SMTP_PORT", "587") or "587").strip())

            msg = MIMEMultipart()
            msg['From'] = self.gmail_user
            msg['To'] = self.recipient_email
            msg['Subject'] = f"[FastTrade] {subject}"
            
            # Add HTML formatting
            html_body = f"""
            <html>
                <body style="font-family: Arial, sans-serif; padding: 20px;">
                    <div style="background: #1e293b; color: #e2e8f0; padding: 20px; border-radius: 8px;">
                        <h2 style="color: #10b981; margin-top: 0;">FastTrade Alert</h2>
                        <pre style="background: #0f172a; padding: 15px; border-radius: 4px; white-space: pre-wrap;">
{body}
                        </pre>
                        <hr style="border-color: #334155; margin: 20px 0;">
                        <p style="color: #94a3b8; font-size: 12px;">
                            This is an automated alert from your FastTrade system.
                            <br>Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}
                        </p>
                    </div>
                </body>
            </html>
            """
            
            msg.attach(MIMEText(html_body, 'html'))
            
            # Connect and send
            with smtplib.SMTP(server_host, server_port) as server:
                server.starttls()
                server.login(self.gmail_user, self.gmail_password)
                server.send_message(msg)
            
            logger.info(f"✅ Email sent: {subject}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send email: {e}", exc_info=True)
    
    # ============================
    # IN-APP NOTIFICATION MANAGEMENT
    # ============================
    
    def get_unread_notifications(self, limit: int = 50) -> List[Dict]:
        """Get unread in-app notifications"""
        from app.db.models_notification import Notification
        
        try:
            notifications = (
                self.db.query(Notification)
                .filter(Notification.read == False)
                .order_by(Notification.created_at.desc())
                .limit(limit)
                .all()
            )
            
            return [
                {
                    "id": n.id,
                    "type": n.type,
                    "title": n.title,
                    "message": n.message,
                    "priority": n.priority,
                    "metadata": getattr(n, 'data', None) or {},
                    "created_at": n.created_at.isoformat(),
                }
                for n in notifications
            ]
            
        except Exception as e:
            logger.error(f"Failed to fetch notifications: {e}")
            return []
    
    def mark_as_read(self, notification_ids: List[int]):
        """Mark notifications as read"""
        from app.db.models_notification import Notification
        
        try:
            self.db.query(Notification).filter(
                Notification.id.in_(notification_ids)
            ).update({"read": True}, synchronize_session=False)
            
            self.db.commit()
            logger.info(f"Marked {len(notification_ids)} notifications as read")
            
        except Exception as e:
            logger.error(f"Failed to mark notifications as read: {e}")
            self.db.rollback()
    
    def clear_old_notifications(self, days: int = 30):
        """Clear notifications older than N days"""
        from app.db.models_notification import Notification
        from datetime import timedelta
        from app.core.utils.time import now_ist
        
        try:
            cutoff = now_ist() - timedelta(days=days)
            
            deleted = self.db.query(Notification).filter(
                Notification.created_at < cutoff
            ).delete()
            
            self.db.commit()
            logger.info(f"Cleared {deleted} old notifications")
            
        except Exception as e:
            logger.error(f"Failed to clear old notifications: {e}")
            self.db.rollback()


# ============================
# HELPER FUNCTIONS
# ============================

def get_notification_service(db: Session) -> NotificationService:
    """Factory function to get notification service"""
    return NotificationService(db)
