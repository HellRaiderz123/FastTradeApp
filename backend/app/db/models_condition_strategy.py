"""
DB models for Condition Scanner strategies and their backtest results.
Replaces the condition_strategies.json file.
"""
import json as _json
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, JSON, String, Text

from app.core.utils.time import now_ist
from app.db.session import Base


def _parse_json(value):
    if isinstance(value, str):
        try:
            return _json.loads(value)
        except Exception:
            return {}
    return value if value is not None else {}


class ConditionStrategy(Base):
    __tablename__ = "condition_strategies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, default="")
    strategy_type = Column(String, default="Equity Swing")
    direction = Column(String, default="BUY")
    timeframe = Column(String, default="1 Hour")
    universe = Column(String, default="NIFTY50")
    instruments = Column(JSON, default=list)       # list of symbols (empty = scan universe)
    entry_conditions = Column(JSON, nullable=False) # list of condition dicts
    exit_config = Column(JSON, nullable=False)      # ExitConfig dict
    is_active = Column(Boolean, default=True)
    auto_scan_enabled = Column(Boolean, default=False)
    auto_amount = Column(Float, default=10000.0)

    # Scan metadata
    last_scan = Column(DateTime(timezone=True), nullable=True)
    last_signal_count = Column(Integer, default=0)

    # Backtest metadata (lightweight — full result in ConditionStrategyBacktest)
    last_backtest_at = Column(DateTime(timezone=True), nullable=True)
    last_backtest_id = Column(Integer, nullable=True)  # FK to ConditionStrategyBacktest.id

    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)

    @property
    def entry_conditions_list(self):
        return _parse_json(self.entry_conditions) or []

    @property
    def exit_config_dict(self):
        return _parse_json(self.exit_config) or {}

    @property
    def instruments_list(self):
        return _parse_json(self.instruments) or []

    def to_dict(self, include_backtest=True):
        """Serialize to the same shape the frontend and scanner code expect."""
        d = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "strategy_type": self.strategy_type,
            "direction": self.direction,
            "timeframe": self.timeframe,
            "universe": self.universe,
            "instruments": self.instruments_list,
            "entry_conditions": self.entry_conditions_list,
            "exit_config": self.exit_config_dict,
            "is_active": self.is_active,
            "auto_scan_enabled": self.auto_scan_enabled,
            "auto_amount": self.auto_amount,
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "last_signal_count": self.last_signal_count or 0,
            "last_backtest_at": self.last_backtest_at.isoformat() if self.last_backtest_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        return d


class ConditionStrategyBacktest(Base):
    __tablename__ = "condition_strategy_backtests"

    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, index=True, nullable=False)
    strategy_name = Column(String, nullable=False)

    start_date = Column(String, nullable=False)   # ISO date string
    end_date = Column(String, nullable=False)
    initial_capital = Column(Float, default=100000.0)
    final_capital = Column(Float, nullable=True)

    # Full result payload (summary + equity_curve + per_symbol + all_trades)
    result = Column(JSON, nullable=False)

    created_at = Column(DateTime(timezone=True), default=now_ist)

    @property
    def result_dict(self):
        return _parse_json(self.result) or {}
