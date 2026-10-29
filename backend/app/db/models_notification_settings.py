from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.db.session import Base
from app.core.utils.time import now_ist


class NotificationSettings(Base):
    __tablename__ = "notification_settings"

    id                   = Column(Integer, primary_key=True, index=True)
    # Gmail
    gmail_user           = Column(String, nullable=True)   # encrypted
    gmail_app_password   = Column(String, nullable=True)   # encrypted
    alert_email          = Column(String, nullable=True)
    gmail_enabled        = Column(Boolean, default=True)
    # Telegram
    telegram_bot_token   = Column(String, nullable=True)   # encrypted
    telegram_chat_id     = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)
