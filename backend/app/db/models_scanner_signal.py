import json as _json
from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, JSON, String

from app.core.utils.time import now_ist
from app.db.session import Base


def _parse_json_field(value):
    """Return value as dict/list, parsing string if needed (migration guard)."""
    if isinstance(value, str):
        try:
            return _json.loads(value)
        except Exception:
            return {}
    return value if value is not None else {}


class ScannerSignalHistory(Base):
    """Persistent history for generated and executed condition-scanner signals."""

    __tablename__ = "scanner_signal_history"

    id = Column(Integer, primary_key=True)

    strategy_id = Column(Integer, index=True, nullable=True)
    strategy_name = Column(String, index=True, nullable=False)
    symbol = Column(String, index=True, nullable=False)
    direction = Column(String, index=True, nullable=False)
    timeframe = Column(String, nullable=True)
    universe = Column(String, nullable=True)
    source = Column(String, index=True, default="CONDITION_SCANNER")

    status = Column(String, index=True, default="SIGNAL_GENERATED")
    signal_date = Column(Date, index=True, nullable=False)
    first_seen_at = Column(DateTime(timezone=True), default=now_ist, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), default=now_ist, nullable=False)
    executed_at = Column(DateTime(timezone=True), nullable=True)

    trigger_count = Column(Integer, default=1)
    auto_execute = Column(Boolean, default=False)
    execution_mode = Column(String, nullable=True)
    quantity = Column(Integer, nullable=True)
    ltp = Column(Float, nullable=True)
    change_percent = Column(Float, nullable=True)
    order_id = Column(String, nullable=True)

    indicators_json = Column(JSON, nullable=True)
    signal_payload = Column(JSON, nullable=True)
    execution_payload = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)