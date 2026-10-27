from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint
from app.db.session import Base
from app.core.utils.time import now_ist


class IndstocksInstrument(Base):
    """
    Persistent contract table for INDstocks instruments.
    Synced from /market/instruments?source={equity,fno,index} on startup + daily.
    Eliminates hardcoded scrip-code maps in market_data.py.
    """
    __tablename__ = "indstocks_instruments"

    id         = Column(Integer, primary_key=True)
    symbol     = Column(String, nullable=False, index=True)   # e.g. RELIANCE, NIFTY 50
    scrip_code = Column(String, nullable=False)               # e.g. NSE_2885
    exchange   = Column(String, nullable=False)               # NSE / BSE
    source     = Column(String, nullable=False)               # equity / fno / index
    synced_at  = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)

    __table_args__ = (
        UniqueConstraint("symbol", "source", name="uq_instrument_symbol_source"),
    )
