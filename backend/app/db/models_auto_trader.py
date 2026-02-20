"""
Auto-Trader Database Models
----------------------------
Stores auto-trader configuration and action log.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Float, Text
from app.db.session import Base
from app.core.utils.time import now_ist


class AutoTraderConfig(Base):
    """Persistent auto-trader configuration."""
    __tablename__ = "auto_trader_config"

    id = Column(Integer, primary_key=True)

    # What to trade
    underlyings = Column(JSON, default=["NIFTY"])  # e.g. ["NIFTY", "BANKNIFTY"]

    # Capital & lots
    capital = Column(Float, default=100000)
    lots = Column(Integer, default=1)

    # Risk parameters
    risk_mode = Column(String, default="BALANCED")       # CONSERVATIVE / BALANCED / AGGRESSIVE
    min_confidence = Column(Float, default=70)
    max_open_positions = Column(Integer, default=3)
    max_daily_loss = Column(Float, default=5000)          # max aggregate loss before halting

    # SL / TP defaults (absolute ₹)
    default_tp = Column(Float, nullable=True)             # None = auto-calculate
    default_sl = Column(Float, nullable=True)             # None = auto-calculate
    trailing_sl_pct = Column(Float, default=0)            # 0 = off

    # Execution mode
    mode = Column(String, default="PAPER")               # PAPER / DRY_RUN / LIVE
    enabled = Column(Boolean, default=False)             # master on/off

    # Signal reversal handling
    auto_exit_on_reversal = Column(Boolean, default=True)    # exit if TA flips against position
    auto_hedge_on_reversal = Column(Boolean, default=False)  # hedge instead of exit
    reversal_confidence_threshold = Column(Float, default=65) # min confidence to act on reversal

    # Schedule
    scan_interval_sec = Column(Integer, default=30)       # how often to scan (seconds)
    market_hours_only = Column(Boolean, default=True)     # only trade 9:15-15:15

    # State
    status = Column(String, default="STOPPED")           # RUNNING / STOPPED / PAUSED / ERROR
    last_scan_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    daily_pnl = Column(Float, default=0)                 # tracked daily
    daily_trades = Column(Integer, default=0)            # tracked daily

    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)


class AutoTraderLog(Base):
    """Log of every action taken by the auto-trader."""
    __tablename__ = "auto_trader_log"

    id = Column(Integer, primary_key=True)

    # What happened
    action = Column(String)          # SCAN, ENTRY, EXIT, HEDGE, REVERSAL_EXIT, SKIP, ERROR, START, STOP
    underlying = Column(String, nullable=True)
    strategy = Column(String, nullable=True)

    # Details
    reason = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)     # flexible payload — signal data, PnL, etc.

    # Linked intent (if an order was placed)
    intent_id = Column(String, nullable=True)
    run_id = Column(Integer, nullable=True)

    # Outcome
    pnl_impact = Column(Float, nullable=True)
    severity = Column(String, default="INFO")   # INFO, WARNING, ERROR, SUCCESS

    created_at = Column(DateTime(timezone=True), default=now_ist)
