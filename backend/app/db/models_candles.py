from sqlalchemy import Column, Integer, String, Float, DateTime, Index, Date
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


class CandleDaily(Base):
    __tablename__ = "candles_daily"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)      # NIFTY, SBIN, etc
    date = Column(Date, index=True)          # Trade date

    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)

    created_at = Column(DateTime(timezone=True), default=now_ist)


class OptionHistoricalCandle(Base):
    """Store historical option chain candles for backtesting expired contracts"""
    __tablename__ = "option_historical_candles"

    id = Column(Integer, primary_key=True)
    
    # Option identification
    tradingsymbol = Column(String, index=True)  # NIFTY24FEB48000CE
    instrument_token = Column(Integer, index=True)  # Zerodha token
    underlying = Column(String, index=True)  # NIFTY, BANKNIFTY, FINNIFTY
    expiry = Column(Date, index=True)  # 2024-02-15
    strike = Column(Float, index=True)  # 48000
    option_type = Column(String, index=True)  # CE or PE
    
    # OHLCV data
    timestamp = Column(DateTime(timezone=True), index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=now_ist)


Index("ix_candles_symbol_ts", Candle15m.symbol, Candle15m.timestamp, unique=True)
Index("ix_candles_daily_symbol_date", CandleDaily.symbol, CandleDaily.date, unique=True)
Index("ix_option_candles_symbol_ts", OptionHistoricalCandle.tradingsymbol, OptionHistoricalCandle.timestamp, unique=True)
Index("ix_option_candles_expiry_strike", OptionHistoricalCandle.underlying, OptionHistoricalCandle.expiry, OptionHistoricalCandle.strike, OptionHistoricalCandle.option_type)

