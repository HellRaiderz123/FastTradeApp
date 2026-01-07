"""
PROFITABLE MOCK STRATEGY for testing backtest engine
Instead of random trades, this uses simple profitable logic
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ProfitableMockStrategy:
    """Simple but profitable strategy for backtest validation"""
    
    def __init__(self):
        self.candle_history = []
        self.highest_price = None
        self.lowest_price = None
    
    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate signals based on support/resistance bounce.
        
        Logic:
        - Track highest and lowest prices in last 20 candles
        - Buy near support (low), sell near resistance (high)
        - Simple but has an edge
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
            
            # Track history
            self.candle_history.append(candle)
            if len(self.candle_history) > 20:
                self.candle_history = self.candle_history[-20:]
            
            close_price = candle.get("close", 0)
            
            # Calculate support and resistance
            if len(self.candle_history) >= 10:
                closes = [c.get("close", 0) for c in self.candle_history]
                support = min(closes)
                resistance = max(closes)
                mid_point = (support + resistance) / 2
                
                # Buy near support (bottom 20%)
                if close_price < support + (resistance - support) * 0.2:
                    return {
                        "strategy": "BULLISH",
                        "signal": "BULLISH",
                        "approved": True,
                        "reason": "Buy at support",
                        "confidence": 80,
                        "ticket": {},
                    }
                
                # Sell near resistance (top 20%)
                elif close_price > support + (resistance - support) * 0.8:
                    return {
                        "strategy": "BEARISH",
                        "signal": "BEARISH",
                        "approved": True,
                        "reason": "Sell at resistance",
                        "confidence": 80,
                        "ticket": {},
                    }
            
            return {
                "strategy": "RANGE",
                "approved": False,
                "reason": "No clear setup",
                "confidence": 0,
            }
            
        except Exception as e:
            logger.error(f"Strategy error: {e}")
            return {
                "strategy": "RANGE",
                "approved": False,
                "reason": str(e),
                "confidence": 0,
            }


if __name__ == "__main__":
    print("""
    PROFITABLE MOCK STRATEGY
    =======================
    
    This strategy buys near support and sells near resistance.
    It has a built-in edge and should show positive returns in backtest.
    
    To use this in backtest, replace BacktestMockStrategy with ProfitableMockStrategy
    in app/core/backtest/engine.py line 65.
    """)
