"""
Notification Model
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON
from app.db.session import Base
from app.core.utils.time import now_ist


class Notification(Base):
    """In-app notifications"""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    
    # Notification details
    type = Column(String, index=True)  # trade_executed, sl_hit, etc.
    title = Column(String)
    message = Column(String)
    priority = Column(String)  # low, medium, high, critical
    
    # Metadata (JSON) - keep column name 'metadata' but avoid reserved attribute name
    data = Column("metadata", JSON, default=dict)
    
    # Status
    read = Column(Boolean, default=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=now_ist, index=True)
