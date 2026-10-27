"""
SQLAlchemy model for caching Indian Stocks Fundamentals API responses.
Cache TTL: 90 days (refreshes after quarterly results ~every 90 days).
"""
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Text, DateTime, JSON
from app.db.models import Base


class FundamentalsCache(Base):
    __tablename__ = "fundamentals_cache"

    symbol = Column(String(30), primary_key=True, index=True)
    # Top ratios from API
    pe_ratio = Column(Float, nullable=True)
    pb_ratio = Column(Float, nullable=True)  # price / book value
    roe = Column(Float, nullable=True)
    roce = Column(Float, nullable=True)
    market_cap = Column(Float, nullable=True)
    current_price = Column(Float, nullable=True)
    book_value = Column(Float, nullable=True)
    dividend_yield = Column(Float, nullable=True)
    face_value = Column(Float, nullable=True)
    high_low_52w = Column(String(50), nullable=True)  # raw string e.g. "3,350 / 2,000"
    week52_high = Column(Float, nullable=True)
    week52_low = Column(Float, nullable=True)
    # Company info
    company_name = Column(String(200), nullable=True)
    about = Column(Text, nullable=True)
    industry = Column(String(100), nullable=True)
    sector = Column(String(100), nullable=True)
    # Computed financial metrics
    opm_pct = Column(Float, nullable=True)       # Operating Profit Margin %
    npm_pct = Column(Float, nullable=True)       # Net Profit Margin %
    eps = Column(Float, nullable=True)           # EPS (latest annual)
    debt_to_equity = Column(Float, nullable=True)
    # Peer comparison (JSON list)
    peer_comparison = Column(JSON, nullable=True)
    # Rich data sections
    key_points = Column(Text, nullable=True)
    shareholding_quarterly = Column(JSON, nullable=True)
    annual_reports = Column(JSON, nullable=True)
    credit_ratings = Column(JSON, nullable=True)
    quarterly_results = Column(JSON, nullable=True)  # last 8 quarters
    pnl_annual = Column(JSON, nullable=True)          # last 5 years P&L
    # Full raw response (for future use)
    raw_ref = Column(JSON, nullable=True)
    # Cache metadata
    cached_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    source = Column(String(50), default="yashsarawgi", nullable=False)
