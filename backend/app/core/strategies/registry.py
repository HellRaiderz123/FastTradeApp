"""
Strategy Registry System
Enables multi-strategy support without code changes
"""

from typing import Dict, Type, List, Any
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """Interface for all trading strategies"""
    
    @abstractmethod
    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute strategy logic.
        
        Args:
            context: {
                underlying: str,
                parameters: Dict,
                config_id: int (optional)
            }
        
        Returns:
            {
                approved: bool,
                strategy: str,
                reason: str,
                signal: Dict,
                context: Dict,
                ticket: Dict (if approved),
                risk_metrics: Dict
            }
        """
        pass


class StrategyRegistry:
    """Central registry for all strategies"""
    
    _strategies: Dict[str, Type[BaseStrategy]] = {}
    
    @classmethod
    def register(cls, name: str, strategy_class: Type[BaseStrategy]) -> None:
        """Register a strategy"""
        logger.info(f"Registering strategy: {name}")
        cls._strategies[name] = strategy_class
    
    @classmethod
    def get(cls, name: str) -> Type[BaseStrategy]:
        """Get strategy class by name"""
        if name not in cls._strategies:
            raise ValueError(f"Strategy not found: {name}. Available: {list(cls._strategies.keys())}")
        return cls._strategies[name]
    
    @classmethod
    def list_all(cls) -> List[str]:
        """List all registered strategies"""
        return list(cls._strategies.keys())
    
    @classmethod
    def list_with_metadata(cls) -> List[Dict]:
        """List strategies with metadata"""
        return [
            {
                'name': name,
                'class': strategy_class.__name__,
            }
            for name, strategy_class in cls._strategies.items()
        ]


def register_default_strategies():
    """Register built-in strategies at startup"""
    from app.core.strategies.option_spread_15m.engine import OptionSpread15m
    from app.core.strategies.option_spread_custom.engine import OptionSpreadCustom
    
    StrategyRegistry.register('option_spread_15m', OptionSpread15m)
    StrategyRegistry.register('option_spread_custom', OptionSpreadCustom)
    logger.info("✅ Default strategies registered")


# Auto-register on import
try:
    register_default_strategies()
except Exception as e:
    logger.warning(f"⚠️ Could not auto-register strategies: {e}")
