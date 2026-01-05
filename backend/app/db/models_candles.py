from sqlalchemy import Column, Integer, String, Float, DateTime, Index
from app.db.session import Base
from app.core.utils.time import now_ist

class Candle15m(Base):
    __tablename__ = "candles_15m"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)      # NIFTY
    timestamp = Column(DateTime(timezone=True), index=True)

    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)

    created_at = Column(DateTime(timezone=True), default=now_ist)

Index("ix_candles_symbol_ts", Candle15m.symbol, Candle15m.timestamp, unique=True)
