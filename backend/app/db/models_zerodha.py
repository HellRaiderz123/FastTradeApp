from sqlalchemy import Column, Integer, String, DateTime
from app.db.session import Base
from app.core.utils.time import now_ist


class ZerodhaSession(Base):
    """Store Zerodha OAuth session tokens in DB instead of .env"""
    __tablename__ = "zerodha_sessions"

    id = Column(Integer, primary_key=True)
    
    # Tokens
    access_token = Column(String, nullable=False, unique=True, index=True)
    user_id = Column(String, nullable=True)  # Optional: user ID from Zerodha
    
    # Lifecycle
    created_at = Column(DateTime(timezone=True), default=now_ist)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Track if active
    is_active = Column(Integer, default=1)  # 1 = active, 0 = revoked/expired
