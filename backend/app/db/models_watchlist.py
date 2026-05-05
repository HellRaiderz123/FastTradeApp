"""
Models for custom watchlists
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Boolean
from app.db.session import Base
from app.core.utils.time import now_ist


class Watchlist(Base):
    """User-created watchlists"""
    __tablename__ = "watchlists"

    id = Column(Integer, primary_key=True)
    
    # Identification
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    
    # Symbol list
    symbols = Column(JSON, default=list)  # List of symbols: ["NIFTY", "BANKNIFTY", "RELIANCE", ...]
    
    # Display settings
    color = Column(String, default="#3b82f6")  # Theme color for UI
    icon = Column(String, nullable=True)  # Icon name (lucide-react)
    
    # Metadata
    is_default = Column(Boolean, default=False)  # Mark as default watchlist
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)
    created_by = Column(String, default="user")


class WatchlistAlert(Base):
    """Price alerts for watchlist symbols"""
    __tablename__ = "watchlist_alerts"

    id = Column(Integer, primary_key=True)
    
    # Reference
    watchlist_id = Column(Integer, ForeignKey("watchlists.id"), nullable=True)
    
    # Alert details
    symbol = Column(String, nullable=False, index=True)
    alert_type = Column(String, nullable=False)  # PRICE_ABOVE, PRICE_BELOW, PERCENT_CHANGE
    
    # Trigger conditions
    target_price = Column(Float, nullable=True)  # For PRICE_ABOVE/BELOW
    percent_change = Column(Float, nullable=True)  # For PERCENT_CHANGE
    
    # Status
    is_active = Column(Boolean, default=True)
    triggered = Column(Boolean, default=False)
    triggered_at = Column(DateTime(timezone=True), nullable=True)
    
    # Notification
    notify_email = Column(Boolean, default=False)
    notify_app = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)
