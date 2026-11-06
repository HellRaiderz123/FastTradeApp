from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, Index
from app.db.session import Base
from app.core.utils.time import now_ist


class NseFilingAnalysis(Base):
    """
    Stores PDF analysis results for HIGH-impact NSE filings on NIFTY500 stocks.
    One row per filing (symbol + headline dedup key).
    """
    __tablename__ = "nse_filing_analysis"

    id              = Column(Integer, primary_key=True)
    symbol          = Column(String, nullable=False, index=True)
    company         = Column(String, nullable=False)
    headline        = Column(String, nullable=False)
    category        = Column(String)
    impact          = Column(String)                    # HIGH / MEDIUM
    pdf_url         = Column(String)
    published_at    = Column(String)

    # PDF extraction
    pdf_text        = Column(Text)                     # raw extracted text (trimmed)
    pdf_extracted   = Column(Boolean, default=False)

    # Analysis output
    sentiment       = Column(String)                   # BULLISH / BEARISH / NEUTRAL
    sentiment_score = Column(Float)                    # -1.0 to +1.0
    summary         = Column(Text)                     # 2-3 line human-readable summary
    key_numbers     = Column(Text)                     # JSON string of extracted numbers
    signal_tags     = Column(Text)                     # comma-separated: BEAT, MISS, ORDER_WIN, etc.

    # Volume/operator filter result
    passed_filter   = Column(Boolean, default=False)   # True = passed NIFTY500 + volume check
    avg_volume      = Column(Float)                    # 20-day avg volume at time of filing
    filter_reason   = Column(String)                   # why it passed/failed

    analysed_at     = Column(DateTime(timezone=True), default=now_ist)
    dedup_key       = Column(String, unique=True, nullable=False)  # symbol|headline[:80]


Index("ix_filing_analysis_symbol", NseFilingAnalysis.symbol)
Index("ix_filing_analysis_sentiment", NseFilingAnalysis.sentiment)
Index("ix_filing_analysis_analysed_at", NseFilingAnalysis.analysed_at)
