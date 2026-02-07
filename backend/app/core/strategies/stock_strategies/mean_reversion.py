"""
mean_reversion.py
-----------------
Mean reversion stock trading strategy.

Logic:
1. Signal: BUY when price < 20-MA and RSI < 40 (oversold)
2. Signal: SELL when price > 20-MA and RSI > 70 (overbought)
3. Entry at 20-MA level (limit order)
4. Stop loss: Below support level (2-3%)
5. Target: Previous high or 1.5-2% above entry

Suitable for: Range-bound NIFTY 50 stocks
"""

from typing import Dict, Any, List

from app.core.strategies.base_strategy import (
    BaseStrategy,
    StrategyType,
    StrategyLeg,
)
from app.core.signals.base import Signal, AssetType, SignalStrength


class MeanReversionStrategy(BaseStrategy):
    """Mean reversion trading strategy for stocks"""
    
    def __init__(self):
        super().__init__(
            name="StockMeanReversion15m",
            strategy_type=StrategyType.MEAN_REVERSION,
            asset_types=[AssetType.STOCK]
        )
        self.min_confidence = 60
        self.rsi_oversold = 40
        self.rsi_overbought = 70
        self.risk_percent = 3.0  # 3% stop loss (wider for reversions)
        self.reward_multiple = 1.5
    
    def initialize(self) -> bool:
        """Validate configuration"""
        if not self.config:
            self.config = {
                "min_confidence": self.min_confidence,
                "rsi_oversold": self.rsi_oversold,
                "rsi_overbought": self.rsi_overbought,
                "risk_percent": self.risk_percent,
                "reward_multiple": self.reward_multiple,
            }
        return True
    
    def evaluate_signal(self, signal: Signal) -> bool:
        """
        Evaluate if signal meets mean reversion requirements.
        
        Checks:
        - Asset type is STOCK
        - Confidence >= min_confidence
        - Signal indicates extreme RSI (oversold/overbought)
        - Price is away from 20-MA
        - Quality score >= 3
        """
        if signal.asset_type != AssetType.STOCK:
            return False
        
        if signal.confidence < self.min_confidence:
            return False
        
        # Check RSI extremes
        rsi = signal.indicators.get("rsi")
        if rsi is None:
            return False
        
        if signal.signal == SignalStrength.BUY:
            # Buying oversold bounce
            if rsi > self.rsi_oversold:
                return False
        elif signal.signal == SignalStrength.SELL:
            # Selling overbought decline
            if rsi < self.rsi_overbought:
                return False
        else:
            return False
        
        # Check price is away from 20-MA
        close = signal.indicators.get("close", 0)
        sma20 = signal.indicators.get("sma_20")
        if close and sma20:
            distance = abs(close - sma20) / sma20
            if distance < 0.01:  # Price not enough away from MA
                return False
        
        # Quality check
        if signal.quality_score < 3:
            return False
        
        return True
    
    def generate_legs(self, signal: Signal, market_data: Dict[str, Any] = None, **kwargs) -> List[StrategyLeg]:
        """
        Generate entry leg targeting mean (20-MA).
        
        For BUY: Target price is 20-MA, stop is below support
        For SELL: Target price is 20-MA, stop is above resistance
        """
        current_price = signal.indicators.get("close", 0)
        sma20 = signal.indicators.get("sma_20")
        
        if not current_price or not sma20:
            return []
        
        action = "BUY" if signal.signal == SignalStrength.BUY else "SELL"
        quantity = kwargs.get("quantity", 1)
        
        # Entry at 20-MA (mean level)
        entry_price = sma20
        
        # Stop loss below/above support/resistance
        if action == "BUY":
            # Support is previous low or ~3% below entry
            stop_loss = entry_price * (1 - self.risk_percent / 100)
            target = current_price * (1 + (self.risk_percent * self.reward_multiple / 100))
        else:  # SELL
            # Resistance is previous high or ~3% above entry
            stop_loss = entry_price * (1 + self.risk_percent / 100)
            target = current_price * (1 - (self.risk_percent * self.reward_multiple / 100))
        
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
        """Calculate risk metrics for mean reversion trade"""
        if not legs:
            return {}
        
        leg = legs[0]
        entry = leg.entry_price
        stoploss = leg.stop_loss or entry * 0.97
        target = leg.take_profit or entry * 1.03
        
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
        """Validate mean reversion risk"""
        max_loss = risk_metrics.get("max_loss", 0)
        rr_ratio = risk_metrics.get("risk_reward_ratio", 0)
        
        if max_loss > 1500:  # Slightly higher for reversions
            return False
        
        if rr_ratio < 1.0:
            return False
        
        return True
