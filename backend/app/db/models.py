from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, Date
from datetime import datetime

from app.db.session import Base
from app.core.utils.time import now_ist


class StrategyRun(Base):
    __tablename__ = "strategy_runs"

    id = Column(Integer, primary_key=True, index=True)

    # Meta
    strategy = Column(String, index=True)
    underlying = Column(String, index=True)
    approved = Column(Boolean)
    reason = Column(String)

    # Risk
    risk_pct = Column(Float)
    max_loss = Column(Float)

    # Strikes / ticket
    ticket = Column(JSON, nullable=True)

    # Signal & context (full snapshot)
    signal = Column(JSON)
    context = Column(JSON)

    # Timestamp
    created_at = Column(DateTime(timezone=True), default=now_ist)

    unrealized_pnl = Column(Float, nullable=True)
    mtm = Column(Float, nullable=True)
    last_mtm_at = Column(DateTime(timezone=True), nullable=True)
    pnl = Column(Float, nullable=True)


class VixHistoric(Base):
    """Store historic VIX data for IV Rank calculation."""
    __tablename__ = "vix_historic"

    id = Column(Integer, primary_key=True, index=True)
    
    # Data point
    trade_date = Column(Date, index=True, unique=True)  # One entry per day
    india_vix = Column(Float, nullable=False)
    
    # Calculated percentiles (updated daily)
    vix_52w_high = Column(Float, nullable=True)
    vix_52w_low = Column(Float, nullable=True)
    iv_rank = Column(Float, nullable=True)  # (Current - 52w_low) / (52w_high - 52w_low) * 100
    
    # Metadata
    source = Column(String)  # 'zerodha', 'nse', 'api', etc.
    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)