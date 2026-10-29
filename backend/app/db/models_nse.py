from sqlalchemy import Column, Integer, String, Date, DateTime, JSON, UniqueConstraint, Index
from app.db.session import Base
from app.core.utils.time import now_ist
from datetime import date as _date


class NseSnapshot(Base):
    """
    Stores a daily snapshot of any NSE data type as JSON.
    One row per (data_type, date) — upserted on each scheduler run.
    data_type values: vix, block_deals, fo_ban, corporate_actions,
                      announcements, insider_trading, short_selling,
                      participant_oi, forthcoming_actions, 52week,
                      market_turnover, ban_history
    """
    __tablename__ = "nse_snapshots"

    id         = Column(Integer, primary_key=True)
    data_type  = Column(String, nullable=False, index=True)
    trade_date = Column(Date, nullable=False, index=True)
    payload    = Column(JSON, nullable=False)
    fetched_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)

    __table_args__ = (
        UniqueConstraint("data_type", "trade_date", name="uq_nse_snapshot_type_date"),
    )


Index("ix_nse_snapshots_type_date", NseSnapshot.data_type, NseSnapshot.trade_date)
