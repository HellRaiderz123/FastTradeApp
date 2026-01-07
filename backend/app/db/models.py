from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, Date
from datetime import datetime

from app.db.session import Base
from app.core.utils.time import now_ist


class StrategyRun(Base):
    __tablename__ = "strategy_runs"

    id = Column(Integer, primary_key=True, index=True)

    # Meta
    strategy = Column(String, index=True)
    underlying = Column(String, index=True)
    approved = Column(Boolean)
    reason = Column(String)

    # Risk
    risk_pct = Column(Float)
    max_loss = Column(Float)

    # Strikes / ticket
    ticket = Column(JSON, nullable=True)

    # Signal & context (full snapshot)
    signal = Column(JSON)
    context = Column(JSON)

    # Timestamp
    created_at = Column(DateTime(timezone=True), default=now_ist)

    unrealized_pnl = Column(Float, nullable=True)
    mtm = Column(Float, nullable=True)
    last_mtm_at = Column(DateTime(timezone=True), nullable=True)
    pnl = Column(Float, nullable=True)


class DailyCapital(Base):
    """Store daily capital details for portfolio growth tracking."""
    __tablename__ = "daily_capital"

    id = Column(Integer, primary_key=True, index=True)
    
    # Date (one record per day)
    trade_date = Column(Date, index=True, unique=True)
    
    # Capital snapshot
    opening_capital = Column(Float)  # Capital at start of day
    closing_capital = Column(Float)  # Capital at end of day
    daily_pnl = Column(Float, default=0.0)  # P&L for the day
    
    # Derived metrics
    daily_return_pct = Column(Float, nullable=True)  # (closing - opening) / opening * 100
    
    # Metadata
    source = Column(String, default="zerodha")  # zerodha, manual, etc.
    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)


class VixHistoric(Base):
    """Store historic VIX data for IV Rank calculation."""
    __tablename__ = "vix_historic"

    id = Column(Integer, primary_key=True, index=True)
    
    # Data point
    trade_date = Column(Date, index=True, unique=True)  # One entry per day
    india_vix = Column(Float, nullable=False)
    
    # Calculated percentiles (updated daily)
    vix_52w_high = Column(Float, nullable=True)
    vix_52w_low = Column(Float, nullable=True)
    iv_rank = Column(Float, nullable=True)  # (Current - 52w_low) / (52w_high - 52w_low) * 100
    
    # Metadata
    source = Column(String)  # 'zerodha', 'nse', 'api', etc.
    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)


class StrategyConfig(Base):
    """User-configured strategy instances"""
    __tablename__ = "strategy_configs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Identification
    name = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    
    # Strategy details
    strategy_type = Column(String)  # option_spread_15m, etc.
    underlying = Column(String)  # NIFTY, BANKNIFTY, FINNIFTY
    
    # Configuration
    parameters = Column(JSON)  # {risk_mode, lots, capital_percent, etc.}
    
    # State
    enabled = Column(Boolean, default=False)
    deployed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)
    created_by = Column(String, default="system")


class BacktestResult(Base):
    """Store backtest results and performance metrics"""
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, index=True)
    
    # References
    strategy_config_id = Column(Integer, nullable=False, index=True)
    
    # Date range
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    
    # Setup
    initial_capital = Column(Float, default=100000)
    
    # Performance Metrics
    total_return_pct = Column(Float)  # (final_equity - initial) / initial * 100
    annual_return_pct = Column(Float)
    sharpe_ratio = Column(Float)
    sortino_ratio = Column(Float)
    max_drawdown_pct = Column(Float)
    calmar_ratio = Column(Float)
    
    # Trade Statistics
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate_pct = Column(Float)  # (winning / total) * 100
    profit_factor = Column(Float)  # (gross_profit / gross_loss)
    
    # P&L Stats
    total_profit = Column(Float, default=0)
    total_loss = Column(Float, default=0)
    avg_win = Column(Float)
    avg_loss = Column(Float)
    largest_win = Column(Float)
    largest_loss = Column(Float)
    
    # Equity Curve
    final_equity = Column(Float)
    peak_equity = Column(Float)
    
    # Detailed Data
    trades = Column(JSON)  # List of trade details [{entry_price, exit_price, pnl, ...}]
    equity_curve = Column(JSON)  # Daily equity values [100000, 101000, ...]
    drawdown_periods = Column(JSON)  # List of drawdown periods
    
    # Status
    status = Column(String, default="completed")  # completed, running, failed
    error = Column(String, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)


class BacktestTrade(Base):
    """Store individual trades from backtests for detailed analysis"""
    __tablename__ = "backtest_trades"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Reference
    backtest_result_id = Column(Integer, nullable=False, index=True)
    
    # Trade Details
    entry_date = Column(Date, nullable=False)
    exit_date = Column(Date, nullable=True)
    
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    
    quantity = Column(Integer)
    
    # Metrics
    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    
    # Trade Info
    strategy = Column(String)  # Call Spread, Put Spread, etc.
    ticket = Column(JSON)  # Full ticket details
    
    # Status
    status = Column(String)  # open, closed
    
    created_at = Column(DateTime(timezone=True), default=now_ist)