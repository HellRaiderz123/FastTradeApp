from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, ForeignKey
from app.db.session import Base
from sqlalchemy import Float
import json as _json

from app.core.utils.time import now_ist

def _parse_json_field(value):
    """Parse a JSON field that may be a string (migration artifact) or already a dict/list."""
    if isinstance(value, str):
        try:
            return _json.loads(value)
        except Exception:
            return {}
    return value if value is not None else {}

class ExecutionIntent(Base):
    __tablename__ = "execution_intents"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, nullable=False)

    intent_id = Column(String, unique=True, index=True)
    strategy = Column(String)
    underlying = Column(String)
    expiry = Column(String, nullable=True)  # Expiry date for option contracts

    ticket = Column(JSON)

    status = Column(String, default="CONFIRMED")
    executed = Column(Boolean, default=False)

    expires_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), default=now_ist)

    avg_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)

    execution_result = Column(JSON, nullable=True)

    last_mtm_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    tp = Column(Float, nullable=True)   # take profit (absolute ₹)
    sl = Column(Float, nullable=True)   # stop loss (absolute ₹)
    trailing_sl_pct = Column(Float, nullable=True)  # trailing stop loss as % (e.g., 5.0 for 5%)
    exit_reason = Column(String, nullable=True)

    entry_credit = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, nullable=True)
    margin_required = Column(Float, nullable=True)  # Margin blocked by broker (Zerodha)
    max_unrealized_pnl = Column(Float, nullable=True)  # Highest profit reached (for trailing stops)

    @property
    def ticket_dict(self) -> dict:
        """Always returns ticket as a dict, parsing string if needed."""
        return _parse_json_field(self.ticket)

    @property
    def execution_result_dict(self) -> dict:
        """Always returns execution_result as a dict, parsing string if needed."""
        return _parse_json_field(self.execution_result)