from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from app.db.session import Base
from app.core.utils.time import now_ist


class StockHolding(Base):
    """
    Tracks open cash/equity positions created via AI chat or Strategy Scanner.
    Separate from ExecutionIntent (which is for options/spreads).
    """
    __tablename__ = "stock_holdings"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False, index=True)
    direction = Column(String, nullable=False)          # BUY | SELL
    quantity = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=True)
    pnl = Column(Float, default=0.0)

    strategy_name = Column(String, nullable=True)       # scanner strategy or AI_TRADE
    source = Column(String, nullable=False, default="SCANNER")  # SCANNER | AI_CHAT
    execution_mode = Column(String, nullable=True)      # PAPER | LIVE | DRY_RUN
    order_id = Column(String, nullable=True)

    tp_pct = Column(Float, nullable=True)
    sl_pct = Column(Float, nullable=True)
    tsl_pct = Column(Float, nullable=True)

    status = Column(String, default="OPEN")             # OPEN | CLOSED
    exit_price = Column(Float, nullable=True)
    exit_reason = Column(String, nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)

    @property
    def invested_value(self) -> float:
        return round(self.entry_price * self.quantity, 2)

    @property
    def current_value(self) -> float:
        price = self.current_price or self.entry_price
        return round(price * self.quantity, 2)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "direction": self.direction,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "pnl": round(self.pnl or 0.0, 2),
            "invested_value": self.invested_value,
            "current_value": self.current_value,
            "strategy_name": self.strategy_name,
            "source": self.source,
            "execution_mode": self.execution_mode,
            "order_id": self.order_id,
            "tp_pct": self.tp_pct,
            "sl_pct": self.sl_pct,
            "tsl_pct": self.tsl_pct,
            "status": self.status,
            "exit_price": self.exit_price,
            "exit_reason": self.exit_reason,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
