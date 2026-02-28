from sqlalchemy import Column, Integer, String, DateTime, Float, JSON
from app.db.session import Base
from app.core.utils.time import now_ist


class SignalOutcome(Base):
    """Stores signal snapshot and its eventual trade outcome."""
    __tablename__ = "signal_outcomes"

    id = Column(Integer, primary_key=True)

    # Link back to trade intent
    intent_id = Column(String, unique=True, index=True)
    run_id = Column(Integer, index=True)

    # Trade info
    underlying = Column(String, index=True)
    strategy = Column(String, index=True)

    # Signal snapshot
    signal_strength = Column(String, index=True)  # e.g. BULLISH/BEARISH/BUY/SELL
    signal_bias = Column(String, index=True)      # BULLISH/BEARISH/NEUTRAL
    confidence = Column(Float, nullable=True)
    market_mode = Column(String, index=True)
    iv_regime = Column(String, index=True)

    signal_json = Column(JSON, nullable=True)
    context_json = Column(JSON, nullable=True)

    # Entry/exit
    entry_credit = Column(Float, nullable=True)
    entry_time = Column(DateTime(timezone=True), nullable=True)
    exit_time = Column(DateTime(timezone=True), nullable=True)

    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    exit_reason = Column(String, nullable=True)
    outcome = Column(String, nullable=True)  # WIN / LOSS / BREAKEVEN

    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)
