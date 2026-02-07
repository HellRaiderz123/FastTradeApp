"""
trend_following.py
------------------
Trend following strategy for NIFTY 50 stocks.

Logic:
1. Signal: BUY when 20-MA > 50-MA and price > 20-MA (bullish crossover)
2. Signal: SELL when 20-MA < 50-MA and price < 20-MA (bearish crossover)
3. Entry on MA crossover confirmation
4. Stop loss: Below/above 50-MA
5. Target: 2-3x risk, or previous swing high/low

Suitable for: Trending NIFTY 50 stocks
"""

from typing import Dict, Any, List

from app.core.strategies.base_strategy import (
    BaseStrategy,
    StrategyType,
    StrategyLeg,
)
from app.core.signals.base import Signal, AssetType, SignalStrength


class TrendFollowingStrategy(BaseStrategy):
    """Trend following strategy for stocks"""
    
    def __init__(self):
        super().__init__(
            name="StockTrendFollowing15m",
            strategy_type=StrategyType.DIRECTIONAL,
            asset_types=[AssetType.STOCK]
        )
        self.min_confidence = 65
        self.risk_percent = 2.5  # 2.5% stop loss
        self.reward_multiple = 2.0  # 2x risk for target
    
    def initialize(self) -> bool:
        """Validate configuration"""
        if not self.config:
            self.config = {
                "min_confidence": self.min_confidence,
                "risk_percent": self.risk_percent,
                "reward_multiple": self.reward_multiple,
            }
        return True
    
    def evaluate_signal(self, signal: Signal) -> bool:
        """
        Evaluate if signal meets trend following requirements.
        
        Checks:
        - Asset type is STOCK
        - Confidence >= min_confidence
        - Signal is BUY or SELL
        - MAs are in proper alignment (20 > 50 for BUY, 20 < 50 for SELL)
        - Price is on right side of 20-MA
        - Quality score >= 4 (needs more confirmation for trends)
        """
        if signal.asset_type != AssetType.STOCK:
            return False
        
        if signal.confidence < self.min_confidence:
            return False
        
        if signal.signal not in [SignalStrength.BUY, SignalStrength.SELL]:
            return False
        
        # Get MAs
        sma20 = signal.indicators.get("sma_20")
        sma50 = signal.indicators.get("sma_50")
        close = signal.indicators.get("close")
        
        if not all([sma20, sma50, close]):
            return False
        
        # Check MA alignment
        if signal.signal == SignalStrength.BUY:
            # For uptrend: 20-MA > 50-MA and price > 20-MA
            if not (sma20 > sma50 and close > sma20):
                return False
        else:  # SELL
            # For downtrend: 20-MA < 50-MA and price < 20-MA
            if not (sma20 < sma50 and close < sma20):
                return False
        
        # Quality: Needs 4+ checks passed (trend confirmation)
        if signal.quality_score < 4:
            return False
        
        return True
    
    def generate_legs(self, signal: Signal, market_data: Dict[str, Any] = None, **kwargs) -> List[StrategyLeg]:
        """
        Generate entry leg for trend trade.
        
        Entry: On 20-MA level (pullback entry)
        Stop: Below/above 50-MA
        Target: 2x risk
        """
        current_price = signal.indicators.get("close", 0)
        sma20 = signal.indicators.get("sma_20")
        sma50 = signal.indicators.get("sma_50")
        
        if not all([current_price, sma20, sma50]):
            return []
        
        action = "BUY" if signal.signal == SignalStrength.BUY else "SELL"
        quantity = kwargs.get("quantity", 1)
        
        # Entry at 20-MA (pullback entry for trend continuation)
        entry_price = sma20
        
        # Stop below/above 50-MA
        if action == "BUY":
            stop_loss = sma50 * (1 - 0.5 / 100)  # Slightly below 50-MA
            target = entry_price * (1 + (self.risk_percent * self.reward_multiple / 100))
        else:  # SELL
            stop_loss = sma50 * (1 + 0.5 / 100)  # Slightly above 50-MA
            target = entry_price * (1 - (self.risk_percent * self.reward_multiple / 100))
        
        leg = StrategyLeg(
            symbol=signal.symbol,
            action=action,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=target,
        )
        
        return [leg]
    
    def calculate_risk(self, legs: List[StrategyLeg]) -> Dict[str, Any]:
        """Calculate risk metrics for trend trade"""
        if not legs:
            return {}
        
        leg = legs[0]
        entry = leg.entry_price
        stoploss = leg.stop_loss or entry * 0.975
        target = leg.take_profit or entry * 1.05
        
        max_loss = abs(entry - stoploss) * leg.quantity
        max_profit = abs(target - entry) * leg.quantity
        
        risk_reward = max_profit / max_loss if max_loss > 0 else 0
        
        return {
            "max_loss": max_loss,
            "max_profit": max_profit,
            "risk_reward_ratio": round(risk_reward, 2),
            "target": target,
            "stop_loss": stoploss,
            "margin_required": entry * leg.quantity * 0.05,
        }
    
    def validate_risk(self, risk_metrics: Dict[str, Any]) -> bool:
        """Validate trend trade risk"""
        max_loss = risk_metrics.get("max_loss", 0)
        rr_ratio = risk_metrics.get("risk_reward_ratio", 0)
        
        # Trend trades can afford more risk (2:1 or better)
        if max_loss > 2000:
            return False
        
        if rr_ratio < 2.0:  # Want at least 2:1 for trends
            return False
        
        return True
