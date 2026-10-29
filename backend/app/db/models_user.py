from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.db.session import Base
from app.core.utils.time import now_ist


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    username      = Column(String, unique=True, index=True, nullable=False)
    email         = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=False)
    role          = Column(String, default="user")        # admin | user
    is_active     = Column(Boolean, default=True)

    # Per-user preferences (moved from .env)
    active_broker   = Column(String, default="ZERODHA")   # ZERODHA | INDMONEY
    execution_mode  = Column(String, default="PAPER_TRADING")

    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)
