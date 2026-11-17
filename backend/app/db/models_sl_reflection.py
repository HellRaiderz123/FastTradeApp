from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Text
from app.db.session import Base
from app.core.utils.time import now_ist


class SLReflection(Base):
    """Per-trade post-mortem generated after an SL hit."""
    __tablename__ = "sl_reflections"

    id = Column(Integer, primary_key=True)
    intent_id = Column(String, unique=True, index=True, nullable=False)

    # Trade identity
    symbol = Column(String, index=True, nullable=False)
    strategy = Column(String, index=True, nullable=False)
    pnl = Column(Float, nullable=True)

    # Root cause weights (sum to 1.0)
    news_weight = Column(Float, default=0.0)       # sudden filing/news
    technical_weight = Column(Float, default=0.0)  # bad entry setup
    macro_weight = Column(Float, default=0.0)       # VIX spike / FII selling
    iv_weight = Column(Float, default=0.0)          # wrong IV regime for strategy
    timing_weight = Column(Float, default=0.0)      # bad time of day / expiry

    # Primary cause label
    primary_cause = Column(String, nullable=True)   # NEWS | TECHNICAL | MACRO | IV | TIMING

    # Snapshot of conditions at entry
    entry_rsi = Column(Float, nullable=True)
    entry_adx = Column(Float, nullable=True)
    entry_vix = Column(Float, nullable=True)
    entry_iv_regime = Column(String, nullable=True)
    entry_market_mode = Column(String, nullable=True)

    # News context
    news_filing_found = Column(Integer, default=0)  # 1 if a filing was found near SL time
    news_sentiment = Column(String, nullable=True)
    news_tags = Column(String, nullable=True)       # comma-separated signal tags

    # Human-readable summary (LLM or rule-based)
    reflection_text = Column(Text, nullable=True)

    # Raw evidence blobs
    evidence = Column(JSON, nullable=True)

    reflected_at = Column(DateTime(timezone=True), default=now_ist)
