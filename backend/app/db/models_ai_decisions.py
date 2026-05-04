"""
AI Decision Memory — persists every completed TradingAgents analysis.

Used by the multi-agent pipeline to:
  1. Record every BUY/SELL/HOLD decision with full agent reports.
  2. Auto-evaluate outcomes N days later by comparing the decision price
     to the actual closing price (from the candles DB).
  3. Inject past decisions for the same symbol into the Trader agent's
     context so the system learns from its own history.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Text, Index
from app.db.session import Base
from app.core.utils.time import now_ist


class AIDecision(Base):
    """One row per completed TradingAgents pipeline run."""
    __tablename__ = "ai_decisions"

    id = Column(Integer, primary_key=True)

    # Identity
    job_id   = Column(String(36), unique=True, index=True, nullable=False)
    symbol   = Column(String(30), index=True, nullable=False)
    exchange = Column(String(10), index=True, nullable=False, default="NSE")

    # Decision
    action      = Column(String(10), index=True)   # BUY | SELL | HOLD
    confidence  = Column(Float, nullable=True)
    conviction  = Column(String(10), nullable=True) # HIGH | MEDIUM | LOW
    time_horizon = Column(String(20), nullable=True) # INTRADAY | SWING | POSITIONAL
    risk_level  = Column(String(10), nullable=True)
    rationale   = Column(Text, nullable=True)

    # Price at time of decision
    price_at_decision = Column(Float, nullable=True)

    # Suggested levels
    suggested_stop_loss_pct  = Column(Float, nullable=True)
    suggested_target_pct     = Column(Float, nullable=True)

    # Full pipeline reports (JSON blobs)
    technical_report   = Column(JSON, nullable=True)
    news_report        = Column(JSON, nullable=True)
    sentiment_report   = Column(JSON, nullable=True)
    bull_report        = Column(JSON, nullable=True)
    bear_report        = Column(JSON, nullable=True)
    fundamentals_report = Column(JSON, nullable=True)

    # Outcome evaluation (filled later by the cron evaluator)
    outcome_evaluated_at = Column(DateTime(timezone=True), nullable=True)
    price_at_evaluation  = Column(Float, nullable=True)
    actual_return_pct    = Column(Float, nullable=True)  # +ve = price went up
    outcome_correct      = Column(Integer, nullable=True) # 1=correct, 0=wrong, None=pending

    # Reflection injected into future runs for same symbol
    reflection = Column(Text, nullable=True)

    analysed_at  = Column(DateTime(timezone=True), index=True, default=now_ist)
    created_at   = Column(DateTime(timezone=True), default=now_ist)

    __table_args__ = (
        Index("ix_ai_decisions_symbol_analysed", "symbol", "analysed_at"),
    )
