"""
Mock Strategy for Backtesting
Generates deterministic signals based on simple price action
"""

import logging
from typing import Dict, Any, Optional
import random
from datetime import datetime

logger = logging.getLogger(__name__)


class BacktestMockStrategy:
    """Simple strategy for backtest simulation with mean-reversion logic"""
    
    def __init__(self):
        self.last_signal = None
        self.consecutive_signals = 0
        self.candle_history = []
        random.seed(42)  # Deterministic for reproducibility
    
    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate trading signals based on mean reversion + technical analysis.
        
        Context should contain:
        - candle: Current OHLC data
        - underlying: Stock symbol
        - parameters: Strategy parameters
        """
        try:
            candle = context.get("candle", {})
            
            if not candle:
                return {
                    "strategy": "RANGE",
                    "approved": False,
                    "reason": "No candle data",
                    "confidence": 0,
                }
            
            # Track candle history (keep last 20)
            self.candle_history.append(candle)
            if len(self.candle_history) > 20:
                self.candle_history = self.candle_history[-20:]
            
            # Generate signal with better logic
            signal, confidence = self._generate_signal_with_confidence(candle)
            
            return {
                "strategy": signal,
                "signal": signal,
                "approved": signal != "RANGE",
                "reason": f"Mock {signal.lower()} signal (mean-reversion)",
                "confidence": confidence,
                "ticket": {},
            }
        
        except Exception as e:
            logger.error(f"Mock strategy error: {e}")
            return {
                "strategy": "RANGE",
                "approved": False,
                "reason": str(e),
                "confidence": 0,
            }
    
    def _generate_signal_with_confidence(self, candle: Dict[str, Any]) -> tuple:
        """
        Generate signal based on multiple factors.
        Uses trend-following with momentum confirmation.
        
        Returns: (signal, confidence_level)
        """
        open_price = candle.get("open", 0)
        close_price = candle.get("close", 0)
        high_price = candle.get("high", 0)
        low_price = candle.get("low", 0)
        
        if not all([open_price, close_price, high_price, low_price]):
            return "RANGE", 0
        
        # Trend analysis from history
        if len(self.candle_history) >= 10:
            closes = [c.get("close", 0) for c in self.candle_history[-10:]]
            
            # Simple trend: average of last 5 vs last 10
            ma5 = sum(closes[-5:]) / 5
            ma10 = sum(closes) / 10
            
            # Trend-following: Buy if price above MA, Sell if below
            if close_price > ma5 and ma5 > ma10:
                return "BULLISH", 75  # Uptrend
            elif close_price < ma5 and ma5 < ma10:
                return "BEARISH", 75  # Downtrend
        
        # Candle strength analysis
        body = abs(close_price - open_price)
        range_size = high_price - low_price
        
        if range_size == 0:
            return "RANGE", 0
        
        body_ratio = body / range_size
        
        if body_ratio < 0.2:
            # Small body = low confidence
            return "RANGE", 20
        elif body_ratio < 0.5:
            # Medium body = medium confidence
            confidence = 60
        else:
            # Large body = high confidence
            confidence = 75
        
        # Direction: Trend-following
        if close_price > open_price:
            # Green candle = bullish
            return "BULLISH", confidence
        elif close_price < open_price:
            # Red candle = bearish
            return "BEARISH", confidence
        else:
            return "RANGE", confidence // 2


# Register the mock strategy
def register_backtest_strategy():
    """Register mock strategy for backtesting"""
    from app.core.strategies.registry import StrategyRegistry
    
    try:
        StrategyRegistry.register("backtest_mock", BacktestMockStrategy)
        logger.info("✅ Registered backtest_mock strategy")
    except Exception as e:
        logger.warning(f"⚠️ Could not register backtest_mock: {e}")
