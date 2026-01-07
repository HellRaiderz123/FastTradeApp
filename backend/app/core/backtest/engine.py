"""
Backtest Engine - Historical candle replay and trade simulation
"""

import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
import numpy as np
from sqlalchemy.orm import Session

from app.db.models import StrategyConfig, BacktestResult, BacktestTrade
from app.core.strategies.registry import StrategyRegistry
from app.core.data.candles import get_historical_candles
from app.core.utils.time import now_ist

logger = logging.getLogger(__name__)


class Trade:
    """Represents a single trade in the backtest"""
    def __init__(self, entry_date: date, entry_price: float, quantity: int, strategy: str, ticket: Dict):
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.exit_date: Optional[date] = None
        self.exit_price: Optional[float] = None
        self.quantity = quantity
        self.strategy = strategy
        self.ticket = ticket
        self.status = "open"
        self.pnl: Optional[float] = None
        self.pnl_pct: Optional[float] = None
    
    def close(self, exit_date: date, exit_price: float):
        """Close the trade"""
        self.exit_date = exit_date
        self.exit_price = exit_price
        self.status = "closed"
        
        # Calculate P&L
        gross_pnl = (exit_price - self.entry_price) * self.quantity
        # Apply commission (0.1% round trip)
        commission = abs(self.entry_price * self.quantity * 0.001)
        commission += abs(exit_price * self.quantity * 0.001)
        
        self.pnl = gross_pnl - commission
        self.pnl_pct = (self.pnl / (self.entry_price * self.quantity)) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "entry_date": self.entry_date.isoformat(),
            "exit_date": self.exit_date.isoformat() if self.exit_date else None,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "strategy": self.strategy,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "status": self.status,
        }


class BacktestEngine:
    """Simulate strategy execution on historical data"""
    
    def __init__(self, strategy_config: StrategyConfig, db: Session):
        self.config = strategy_config
        self.db = db
        
        # Load the ACTUAL strategy from StrategyRegistry (not a mock)
        from app.core.strategies.registry import StrategyRegistry
        try:
            self.strategy_class = StrategyRegistry.get(strategy_config.strategy_type)
            logger.info(f"✅ Initialized BacktestEngine for {strategy_config.name} (strategy: {strategy_config.strategy_type})")
        except Exception as e:
            logger.warning(f"⚠️ Could not load strategy {strategy_config.strategy_type}: {e}")
            logger.info(f"   Falling back to mock strategy for backtest")
            from app.core.strategies.backtest_mock import BacktestMockStrategy
            self.strategy_class = BacktestMockStrategy
        
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = []
        self.daily_equity: Dict[date, float] = {}
        
        logger.info(f"✅ Initialized BacktestEngine for {strategy_config.name} (using mock strategy)")
    
    def run(
        self,
        start_date: date,
        end_date: date,
        initial_capital: float = 100000,
    ) -> Dict[str, Any]:
        """
        Run backtest on historical data
        
        Args:
            start_date: Start date for backtest
            end_date: End date for backtest
            initial_capital: Starting capital
        
        Returns:
            Dictionary with results and metrics
        """
        try:
            logger.info(f"🔄 Starting backtest: {self.config.name} ({start_date} to {end_date})")
            
            # Initialize
            current_equity = initial_capital
            self.daily_equity[start_date] = initial_capital
            
            # Fetch historical candles
            logger.info(f"📊 Fetching historical candles...")
            candles = self._fetch_candles(start_date, end_date)
            
            if not candles:
                logger.warning(f"❌ No candle data available for {start_date} to {end_date}")
                return {
                    "success": False,
                    "error": "No historical data available",
                    "strategy_config_id": self.config.id,
                    "start_date": start_date,
                    "end_date": end_date,
                }
            
            logger.info(f"✅ Loaded {len(candles)} candles")
            
            # Replay candles
            for idx, candle in enumerate(candles):
                try:
                    current_date = candle.get("date", start_date)
                    candle_close = candle.get("close", 0)
                    
                    # Check stop loss / take profit on open trades
                    open_trade = self._get_open_trade()
                    if open_trade:
                        # Calculate unrealized P&L in percentage
                        pnl_pct = ((candle_close - open_trade.entry_price) / open_trade.entry_price) * 100
                        
                        # Stop loss at -2% or Take profit at +1%
                        if pnl_pct <= -2.0:  # Stop loss
                            open_trade.close(current_date, candle_close)
                            current_equity += open_trade.pnl
                            logger.debug(f"🛑 Stop Loss at {current_date} @ {candle_close}, P&L: {open_trade.pnl}")
                            continue
                        elif pnl_pct >= 1.0:  # Take profit
                            open_trade.close(current_date, candle_close)
                            current_equity += open_trade.pnl
                            logger.debug(f"💰 Take Profit at {current_date} @ {candle_close}, P&L: {open_trade.pnl}")
                            continue
                    
                    # Generate signal using strategy
                    context = {
                        "underlying": self.config.underlying,
                        "parameters": self.config.parameters,
                        "candle": candle,
                        "current_equity": current_equity,
                    }
                    
                    signal = self._generate_signal(context)
                    
                    # Only trade if confidence >= min_confidence (default 60%)
                    min_confidence = self.config.parameters.get("min_confidence", 60)
                    is_confident = signal.get("confidence", 0) >= min_confidence
                    
                    # Process signal - entry/exit logic
                    if signal.get("action") == "BUY" and is_confident and not self._has_open_trade():
                        trade = self._create_trade(candle, signal)
                        self.trades.append(trade)
                        logger.debug(f"📈 Entry at {candle['date']} @ {candle['close']} (confidence: {signal.get('confidence')}%)")
                    
                    elif signal.get("action") == "SELL" and self._has_open_trade():
                        open_trade = self._get_open_trade()
                        if open_trade:
                            open_trade.close(candle["date"], candle["close"])
                            # Update equity
                            current_equity += open_trade.pnl
                            logger.debug(f"📉 Exit at {candle['date']} @ {candle['close']}, P&L: {open_trade.pnl}")
                    
                    # Track daily equity
                    self.daily_equity[current_date] = current_equity
                
                except Exception as e:
                    logger.error(f"❌ Error processing candle {idx}: {e}")
                    continue
            
            # Close any remaining open trades at end
            if self._has_open_trade():
                last_candle = candles[-1]
                open_trade = self._get_open_trade()
                if open_trade:
                    open_trade.close(last_candle["date"], last_candle["close"])
                    current_equity += open_trade.pnl
            
            # Build equity curve
            self.equity_curve = list(self.daily_equity.values())
            
            logger.info(f"✅ Backtest complete: {len(self.trades)} trades, Final equity: ₹{current_equity:,.0f}")
            
            # Calculate metrics
            return self._calculate_results(initial_capital, current_equity)
        
        except Exception as e:
            logger.error(f"❌ Backtest failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "strategy_config_id": self.config.id,
            }
    
    def _fetch_candles(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Fetch historical candles for date range"""
        try:
            candles = get_historical_candles(
                symbol=self.config.underlying,
                start_date=start_date,
                end_date=end_date,
                interval="15minute",
            )
            return candles if candles else []
        except Exception as e:
            logger.error(f"❌ Failed to fetch candles: {e}")
            return []
    
    def _generate_signal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate trading signal using strategy"""
        try:
            if not self.strategy_class:
                return {"action": "HOLD"}
            
            strategy_instance = self.strategy_class()
            result = strategy_instance.run(context)
            
            # Strategy can return either "strategy" or "signal" key
            action = result.get("strategy") or result.get("signal")
            if not action or action == "RANGE":
                action = "HOLD"
            
            # For backtest, convert to BUY/SELL
            if action in ["BULLISH", "BUY_CE"]:
                action = "BUY"
            elif action in ["BEARISH", "BUY_PE"]:
                action = "SELL"
            else:
                action = "HOLD"
            
            return {
                "action": action,
                "reason": result.get("reason", ""),
                "ticket": result.get("ticket"),
                "signal": result.get("signal"),
                "confidence": result.get("confidence", 50),
            }
        except Exception as e:
            logger.debug(f"⚠️ Signal generation error: {e}")
            return {"action": "HOLD"}
    
    def _create_trade(self, candle: Dict[str, Any], signal: Dict[str, Any]) -> Trade:
        """Create new trade from signal"""
        quantity = int(self.config.parameters.get("lots", 1) * 50)  # 50 = lot size
        
        trade = Trade(
            entry_date=candle["date"],
            entry_price=candle["close"],
            quantity=quantity,
            strategy=signal.get("action", "UNKNOWN"),
            ticket=signal.get("ticket", {}),
        )
        
        return trade
    
    def _has_open_trade(self) -> bool:
        """Check if there's an open trade"""
        return any(t.status == "open" for t in self.trades)
    
    def _get_open_trade(self) -> Optional[Trade]:
        """Get the first open trade"""
        for trade in self.trades:
            if trade.status == "open":
                return trade
        return None
    
    def _calculate_results(self, initial_capital: float, final_equity: float) -> Dict[str, Any]:
        """Calculate performance metrics"""
        try:
            from app.core.backtest.metrics import MetricsCalculator
            
            calculator = MetricsCalculator(
                initial_capital=initial_capital,
                final_equity=final_equity,
                equity_curve=self.equity_curve,
                trades=self.trades,
            )
            
            metrics = calculator.calculate_all()
            
            return {
                "success": True,
                "strategy_config_id": self.config.id,
                "start_date": min(self.daily_equity.keys()),
                "end_date": max(self.daily_equity.keys()),
                "initial_capital": initial_capital,
                "final_equity": final_equity,
                "total_return_pct": metrics["total_return_pct"],
                "annual_return_pct": metrics["annual_return_pct"],
                "sharpe_ratio": metrics["sharpe_ratio"],
                "sortino_ratio": metrics["sortino_ratio"],
                "max_drawdown_pct": metrics["max_drawdown_pct"],
                "calmar_ratio": metrics["calmar_ratio"],
                "total_trades": len(self.trades),
                "winning_trades": metrics["winning_trades"],
                "losing_trades": metrics["losing_trades"],
                "win_rate_pct": metrics["win_rate_pct"],
                "profit_factor": metrics["profit_factor"],
                "avg_win": metrics["avg_win"],
                "avg_loss": metrics["avg_loss"],
                "largest_win": metrics["largest_win"],
                "largest_loss": metrics["largest_loss"],
                "total_profit": metrics["total_profit"],
                "total_loss": metrics["total_loss"],
                "peak_equity": metrics["peak_equity"],
                "trades": [t.to_dict() for t in self.trades],
                "equity_curve": self.equity_curve,
                "drawdown_periods": calculator.calculate_drawdown_periods(),
            }
        
        except Exception as e:
            logger.error(f"❌ Metrics calculation failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Metrics calculation failed: {str(e)}",
                "strategy_config_id": self.config.id,
            }
