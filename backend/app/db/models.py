from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON
from datetime import datetime

from app.db.session import Base


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
    created_at = Column(DateTime, default=datetime.utcnow)
