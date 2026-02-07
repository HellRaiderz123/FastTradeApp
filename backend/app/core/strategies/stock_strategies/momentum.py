"""
momentum.py
-----------
Momentum-based stock trading strategy.

Logic:
1. Signal: BUY when RSI > 50 and price > 20-MA (uptrend)
2. Signal: SELL when RSI < 50 and price < 20-MA (downtrend)
3. Entry at market on signal
4. Stop loss: 2% below entry
5. Target: 1.5x stop loss (risk:reward = 1:1.5)

Suitable for: Volatile NIFTY 50 stocks with clear momentum
"""

from typing import Dict, Any, List, Optional

from app.core.strategies.base_strategy import (
    BaseStrategy,
    StrategyType,
    StrategyLeg,
)
from app.core.signals.base import Signal, AssetType, SignalStrength


class MomentumStrategy(BaseStrategy):
    """Momentum-based trading strategy for stocks"""
    
    def __init__(self):
        super().__init__(
            name="StockMomentum15m",
            strategy_type=StrategyType.MOMENTUM,
            asset_types=[AssetType.STOCK]
        )
        self.min_confidence = 65
        self.rsi_threshold = 50
        self.risk_percent = 2.0  # 2% stop loss
        self.reward_multiple = 1.5  # 1.5x risk for target
    
    def initialize(self) -> bool:
        """Validate configuration"""
        if not self.config:
            self.config = {
                "min_confidence": self.min_confidence,
                "rsi_threshold": self.rsi_threshold,
                "risk_percent": self.risk_percent,
                "reward_multiple": self.reward_multiple,
            }
        return True
    
    def evaluate_signal(self, signal: Signal) -> bool:
        """
        Evaluate if signal meets momentum strategy requirements.
        
        Checks:
        - Asset type is STOCK
        - Confidence >= min_confidence
        - Signal is BUY or SELL (not HOLD or NO_TRADE)
        - RSI indicator available
        - Quality score >= 3
        """
        if signal.asset_type != AssetType.STOCK:
            return False
        
        if signal.confidence < self.min_confidence:
            return False
        
        if signal.signal not in [SignalStrength.BUY, SignalStrength.SELL]:
            return False
        
        # Check for RSI in indicators
        rsi = signal.indicators.get("rsi")
        if rsi is None:
            return False
        
        # Quality check
        if signal.quality_score < 3:
            return False
        
        return True
    
    def generate_legs(self, signal: Signal, market_data: Dict[str, Any] = None, **kwargs) -> List[StrategyLeg]:
        """
        Generate single leg for stock momentum trade.
        
        Entry: Current price
        Quantity: From kwargs or default to 1 lot
        Stop loss: 2% below/above entry
        Target: 3% above/below entry (1.5x risk)
        """
        current_price = signal.indicators.get("close", 0)
        if current_price <= 0:
            return []
        
        action = "BUY" if signal.signal == SignalStrength.BUY else "SELL"
        quantity = kwargs.get("quantity", 1)
        
        # Calculate stop loss and target
        if action == "BUY":
            stop_loss = current_price * (1 - self.risk_percent / 100)
            target = current_price * (1 + (self.risk_percent * self.reward_multiple / 100))
        else:  # SELL
            stop_loss = current_price * (1 + self.risk_percent / 100)
            target = current_price * (1 - (self.risk_percent * self.reward_multiple / 100))
        
        leg = StrategyLeg(
            symbol=signal.symbol,
            action=action,
            quantity=quantity,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=target,
        )
        
        return [leg]
    
    def calculate_risk(self, legs: List[StrategyLeg]) -> Dict[str, Any]:
        """
        Calculate risk metrics for momentum trade.
        
        Returns: max_loss, max_profit, risk_reward_ratio, target, stop_loss
        """
        if not legs:
            return {}
        
        leg = legs[0]
        entry = leg.entry_price
        stoploss = leg.stop_loss or entry * 0.98
        target = leg.take_profit or entry * 1.03
        
        # For single stock trade, max loss is 1 lot × risk
        max_loss = abs(entry - stoploss) * leg.quantity
        max_profit = abs(target - entry) * leg.quantity
        
        risk_reward = max_profit / max_loss if max_loss > 0 else 0
        
        return {
            "max_loss": max_loss,
            "max_profit": max_profit,
            "risk_reward_ratio": round(risk_reward, 2),
            "target": target,
            "stop_loss": stoploss,
            "margin_required": entry * leg.quantity * 0.05,  # 5% of notional
        }
    
    def validate_risk(self, risk_metrics: Dict[str, Any]) -> bool:
        """
        Validate risk is within acceptable bounds.
        
        Checks:
        - Max loss < 1000 (conservative limit)
        - Risk:reward ratio >= 1:1
        - Margin required reasonable
        """
        max_loss = risk_metrics.get("max_loss", 0)
        rr_ratio = risk_metrics.get("risk_reward_ratio", 0)
        margin = risk_metrics.get("margin_required", 0)
        
        if max_loss > 1000:  # Max loss limit
            return False
        
        if rr_ratio < 1.0:  # Need at least 1:1
            return False
        
        if margin > 50000:  # Max margin limit
            return False
        
        return True
