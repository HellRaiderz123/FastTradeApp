"""
Stock trading strategies for NIFTY 50 and other stocks.

Included strategies:
- MomentumStrategy: Buy oversold + RSI reversal signals
- MeanReversionStrategy: Trade support/resistance bounces
- TrendFollowingStrategy: Trade MA crossovers
"""

from .momentum import MomentumStrategy
from .mean_reversion import MeanReversionStrategy
from .trend_following import TrendFollowingStrategy

__all__ = [
    "MomentumStrategy",
    "MeanReversionStrategy",
    "TrendFollowingStrategy",
]
