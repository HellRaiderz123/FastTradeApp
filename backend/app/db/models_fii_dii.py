from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Index
from app.db.session import Base
from app.core.utils.time import now_ist


class FiiDiiDaily(Base):
    __tablename__ = "fii_dii_daily"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, unique=True, index=True)  # trade date

    # Cash segment
    fii_buy  = Column(Float)
    fii_sell = Column(Float)
    fii_net  = Column(Float)
    dii_buy  = Column(Float)
    dii_sell = Column(Float)
    dii_net  = Column(Float)

    # F&O segment (nullable — filled when NSE CSV is available)
    fii_idx_fut_long   = Column(Integer)
    fii_idx_fut_short  = Column(Integer)
    fii_idx_fut_net    = Column(Integer)
    fii_stk_fut_long   = Column(Integer)
    fii_stk_fut_short  = Column(Integer)
    fii_stk_fut_net    = Column(Integer)
    fii_idx_call_long  = Column(Integer)
    fii_idx_call_short = Column(Integer)
    fii_idx_call_net   = Column(Integer)
    fii_idx_put_long   = Column(Integer)
    fii_idx_put_short  = Column(Integer)
    fii_idx_put_net    = Column(Integer)
    dii_idx_fut_long   = Column(Integer)
    dii_idx_fut_short  = Column(Integer)
    dii_idx_fut_net    = Column(Integer)

    pcr             = Column(Float)
    sentiment_score = Column(Float)

    created_at  = Column(DateTime(timezone=True), default=now_ist)
    updated_at  = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)


Index("ix_fii_dii_daily_date", FiiDiiDaily.date, unique=True)
