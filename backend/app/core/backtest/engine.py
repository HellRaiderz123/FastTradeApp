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

# Realistic Indian brokerage model (Zerodha-like)
# ₹20 per executed order OR 0.03% (whichever is lower) + regulatory charges
BROKERAGE_PER_ORDER = 20.0   # Zerodha flat fee per order
STT_RATE = 0.000625           # STT on sell side (options: 0.0625% on sell premium)
EXCHANGE_TXN_RATE = 0.0000345 # NSE transaction charges
GST_RATE = 0.18               # GST on brokerage + exchange charges
SEBI_RATE = 0.000001           # SEBI turnover fee
STAMP_DUTY_RATE = 0.00003     # Stamp duty (buy side only)


def _calculate_commission(entry_price: float, exit_price: float, quantity: int) -> float:
    """
    Calculate realistic Indian market trading costs (Zerodha model).
    Returns total round-trip charges.
    """
    buy_turnover = abs(entry_price * quantity)
    sell_turnover = abs(exit_price * quantity)
    total_turnover = buy_turnover + sell_turnover

    # Brokerage: ₹20 per order × 2 sides (or 0.03% whichever is lower)
    brokerage = min(BROKERAGE_PER_ORDER, buy_turnover * 0.0003) + \
                min(BROKERAGE_PER_ORDER, sell_turnover * 0.0003)

    # STT (on sell side only for intraday equity/options)
    stt = sell_turnover * STT_RATE

    # Exchange transaction charges
    exchange = total_turnover * EXCHANGE_TXN_RATE

    # GST on brokerage + exchange charges
    gst = (brokerage + exchange) * GST_RATE

    # SEBI charges
    sebi = total_turnover * SEBI_RATE

    # Stamp duty (buy side only)
    stamp = buy_turnover * STAMP_DUTY_RATE

    return brokerage + stt + exchange + gst + sebi + stamp


class Trade:
    """Represents a single trade in the backtest"""
    def __init__(self, entry_date: date, entry_price: float, quantity: int, side: str, strategy: str, ticket: Dict):
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.exit_date: Optional[date] = None
        self.exit_price: Optional[float] = None
        self.quantity = quantity
        self.side = side  # long | short
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
        if self.side == "short":
            gross_pnl = (self.entry_price - exit_price) * self.quantity
        else:
            gross_pnl = (exit_price - self.entry_price) * self.quantity

        # Realistic Indian market commission
        commission = _calculate_commission(self.entry_price, exit_price, self.quantity)
        
        self.pnl = gross_pnl - commission
        self.pnl_pct = (self.pnl / (self.entry_price * self.quantity)) * 100 if self.entry_price > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "entry_date": self.entry_date.isoformat() if hasattr(self.entry_date, 'isoformat') else str(self.entry_date),
            "exit_date": self.exit_date.isoformat() if self.exit_date and hasattr(self.exit_date, 'isoformat') else None,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "side": self.side,
            "strategy": self.strategy,
            "pnl": round(self.pnl, 2) if self.pnl is not None else None,
            "pnl_pct": round(self.pnl_pct, 2) if self.pnl_pct is not None else None,
            "status": self.status,
        }


class BacktestEngine:
    """Simulate strategy execution on historical data"""
    
    def __init__(self, strategy_config: StrategyConfig, db: Session):
        self.config = strategy_config
        self.db = db

        base_symbol = (strategy_config.underlying or "").upper().strip()
        self.backtest_symbol = f"{base_symbol}__BT__{strategy_config.id}"
        
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
        
        # Keep ONE persistent strategy instance so stateful strategies
        # (e.g. moving average crossover) can maintain their candle history.
        self._strategy_instance = self.strategy_class()

        self.trades: List[Trade] = []
        self.equity_curve: List[float] = []

        self.candles_loaded: int = 0
        self.signal_counts: Dict[str, int] = {"BUY": 0, "SELL": 0, "HOLD": 0}
        self.raw_action_counts: Dict[str, int] = {}
        
        # Read SL/TP from strategy parameters (with sane defaults)
        params = strategy_config.parameters or {}
        self.sl_pct = float(params.get("sl_pct", 3) or 3)    # Stop loss %
        self.tp_pct = float(params.get("tp_pct", 3) or 3)    # Take profit %
        
        logger.info(
            "✅ Initialized BacktestEngine for %s (strategy: %s, SL=%.1f%%, TP=%.1f%%)",
            strategy_config.name,
            strategy_config.strategy_type,
            self.sl_pct,
            self.tp_pct,
        )
    
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
            self.candles_loaded = len(candles)

            # Track equity per candle (not just per day) for accurate Sharpe/Sortino
            self.equity_curve = [initial_capital]
            
            # Keep candle history in memory for strategies that need TA
            # (no DB writes needed — 100x faster)
            self._candle_history: List[Dict] = []

            # Replay candles
            for idx, candle in enumerate(candles):
                try:
                    current_date = candle.get("date", start_date)
                    candle_close = candle.get("close", 0)

                    # Accumulate candles in memory (no DB round-trip)
                    self._candle_history.append(candle)
                    
                    # Check stop loss / take profit on open trades
                    open_trade = self._get_open_trade()
                    if open_trade:
                        # Calculate unrealized P&L in percentage
                        if open_trade.side == "short":
                            pnl_pct = ((open_trade.entry_price - candle_close) / open_trade.entry_price) * 100
                        else:
                            pnl_pct = ((candle_close - open_trade.entry_price) / open_trade.entry_price) * 100
                        
                        # Stop loss / Take profit from strategy parameters
                        sl_hit = pnl_pct <= -self.sl_pct
                        tp_hit = pnl_pct >= self.tp_pct

                        if sl_hit:
                            open_trade.close(current_date, candle_close)
                            current_equity += open_trade.pnl
                            logger.debug(f"🛑 Stop Loss at {current_date} @ {candle_close}, P&L: {open_trade.pnl:.2f}")
                            # Don't `continue` — still generate signal for potential re-entry
                        elif tp_hit:
                            open_trade.close(current_date, candle_close)
                            current_equity += open_trade.pnl
                            logger.debug(f"💰 Take Profit at {current_date} @ {candle_close}, P&L: {open_trade.pnl:.2f}")
                    
                    # Generate signal using strategy
                    context = {
                        "underlying": self.config.underlying,
                        "backtest_symbol": self.backtest_symbol,
                        "parameters": self.config.parameters,
                        "candle": candle,
                        "candle_history": self._candle_history,
                        "current_equity": current_equity,
                    }
                    
                    signal = self._generate_signal(context)

                    raw_action = signal.get("action") or "HOLD"
                    self.raw_action_counts[raw_action] = self.raw_action_counts.get(raw_action, 0) + 1
                    
                    # Only trade if confidence >= min_confidence
                    min_confidence = self.config.parameters.get("min_confidence", 55)
                    is_confident = signal.get("confidence", 0) >= min_confidence
                    
                    # Log rejection reasons for debugging
                    if not is_confident and raw_action in ("BUY", "SELL"):
                        logger.debug(
                            f"❌ Trade rejected at {candle.get('date')}: "
                            f"confidence {signal.get('confidence', 0):.1f}% < {min_confidence}% "
                            f"(signal: {raw_action}, quality: {signal.get('quality_score', 0)}/8)"
                        )

                    if raw_action in self.signal_counts:
                        self.signal_counts[raw_action] += 1
                    
                    # Process signal - bidirectional entry/exit logic
                    action = raw_action
                    if action in ("BUY", "SELL") and is_confident:
                        open_trade = self._get_open_trade()
                        if not open_trade:
                            trade = self._create_trade(candle, signal)
                            self.trades.append(trade)
                        else:
                            # Close on opposite signal
                            if (open_trade.side == "long" and action == "SELL") or (
                                open_trade.side == "short" and action == "BUY"
                            ):
                                open_trade.close(candle["date"], candle["close"])
                                current_equity += open_trade.pnl
                    
                    # Track equity every candle for accurate Sharpe/Sortino
                    self.equity_curve.append(current_equity)
                
                except Exception as e:
                    logger.error(f"❌ Error processing candle {idx}: {e}")
                    self.equity_curve.append(current_equity)
                    continue
            
            # Close any remaining open trades at end
            if self._has_open_trade():
                last_candle = candles[-1]
                open_trade = self._get_open_trade()
                if open_trade:
                    open_trade.close(last_candle["date"], last_candle["close"])
                    current_equity += open_trade.pnl
                    self.equity_curve[-1] = current_equity
            
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
            if not self._strategy_instance:
                return {"action": "HOLD"}

            # Many strategies expect config parameters at the top-level payload.
            # Keep original context keys, but also flatten parameters for compatibility.
            payload = dict(context)
            params = context.get("parameters")
            if isinstance(params, dict):
                payload.update(params)

            candle = context.get("candle")
            if isinstance(candle, dict):
                payload.setdefault("spot", candle.get("close"))
                payload.setdefault("backtest", True)

            result = self._strategy_instance.run(payload)
            
            # Strategy can return either "strategy" or "signal" key
            action = result.get("strategy") or result.get("signal")
            if not action or action == "RANGE":
                action = "HOLD"
            
            # For backtest, convert to BUY/SELL
            if action in ["BULLISH", "BUY_CE", "BULL_PUT", "BULL_CALL", "BULL_PUT_SPREAD", "BULL_CALL_SPREAD"]:
                action = "BUY"
            elif action in ["BEARISH", "BUY_PE", "BEAR_CALL", "BEAR_PUT", "BEAR_CALL_SPREAD", "BEAR_PUT_SPREAD"]:
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
        lots = float(self.config.parameters.get("lots", 1) or 1)
        lot_size_map = {
            "NIFTY": 65,
            "BANKNIFTY": 15,
            "FINNIFTY": 40,
        }
        lot_size = int(lot_size_map.get(str(self.config.underlying or "").upper(), 1))
        quantity = int(lots * lot_size)
        
        action = signal.get("action")
        side = "short" if action == "SELL" else "long"

        trade = Trade(
            entry_date=candle["date"],
            entry_price=candle["close"],
            quantity=quantity,
            side=side,
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
            
            # Determine actual calendar date range from candle data
            first_date = None
            last_date = None
            unique_dates = set()
            for t in self.trades:
                if t.entry_date:
                    d = t.entry_date
                    if hasattr(d, 'date'):
                        d = d.date()
                    unique_dates.add(d)
                if t.exit_date:
                    d = t.exit_date
                    if hasattr(d, 'date'):
                        d = d.date()
                    unique_dates.add(d)

            if unique_dates:
                first_date = min(unique_dates)
                last_date = max(unique_dates)
            
            # Compute number of trading days for proper annualization
            trading_days = len(unique_dates) if unique_dates else max(1, len(self.equity_curve) // 26)
            
            calculator = MetricsCalculator(
                initial_capital=initial_capital,
                final_equity=final_equity,
                equity_curve=self.equity_curve,
                trades=self.trades,
                trading_days=trading_days,
            )
            
            metrics = calculator.calculate_all()
            
            return {
                "success": True,
                "strategy_config_id": self.config.id,
                "start_date": first_date or date.today(),
                "end_date": last_date or date.today(),
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
                "candles_loaded": self.candles_loaded,
                "signal_counts": self.signal_counts,
                "raw_action_counts": self.raw_action_counts,
            }
        
        except Exception as e:
            logger.error(f"❌ Metrics calculation failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Metrics calculation failed: {str(e)}",
                "strategy_config_id": self.config.id,
            }
