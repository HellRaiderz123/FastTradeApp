"""
Strategy Registry System
Enables multi-strategy support with backward compatibility.

Supports:
- Old strategy interface (execute via run())
- New BaseStrategy interface (evaluate_and_generate())
"""

from typing import Dict, Type, List, Any, Union
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class StrategyInterface(ABC):
    """Base interface for old-style strategies (backward compatibility)"""
    
    @abstractmethod
    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute strategy logic (old interface).
        
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
    """Central registry for all strategies (old and new)"""
    
    # Old-style strategies (run() method)
    _legacy_strategies: Dict[str, Type[StrategyInterface]] = {}
    
    # New-style strategies (BaseStrategy with evaluate_and_generate())
    _strategies: Dict[str, Any] = {}
    
    @classmethod
    def register_legacy(cls, name: str, strategy_class: Type[StrategyInterface]) -> None:
        """Register a legacy/old-style strategy"""
        logger.info(f"📋 Registering legacy strategy: {name}")
        cls._legacy_strategies[name] = strategy_class
    
    @classmethod
    def register(cls, name: str, strategy_class: Any) -> None:
        """Register a new-style BaseStrategy (or anything with strategy metadata)"""
        logger.info(f"📋 Registering strategy: {name}")
        cls._strategies[name] = strategy_class
    
    @classmethod
    def get(cls, name: str) -> Any:
        """Get strategy class by name (new or legacy)"""
        # Check new strategies first
        if name in cls._strategies:
            return cls._strategies[name]
        
        # Fall back to legacy
        if name in cls._legacy_strategies:
            return cls._legacy_strategies[name]
        
        raise ValueError(
            f"Strategy not found: {name}. "
            f"Available: {list(cls._strategies.keys()) + list(cls._legacy_strategies.keys())}"
        )
    
    @classmethod
    def is_legacy(cls, name: str) -> bool:
        """Check if strategy is legacy style"""
        return name in cls._legacy_strategies
    
    @classmethod
    def list_all(cls) -> List[str]:
        """List all registered strategies"""
        return list(cls._strategies.keys()) + list(cls._legacy_strategies.keys())
    
    @classmethod
    def list_with_metadata(cls) -> List[Dict]:
        """List strategies with metadata"""
        result = [
            {
                'name': name,
                'type': 'NEW',
                'class': strategy_class.__name__ if hasattr(strategy_class, '__name__') else str(strategy_class),
                'instance': isinstance(strategy_class, object),
            }
            for name, strategy_class in cls._strategies.items()
        ]
        
        result.extend([
            {
                'name': name,
                'type': 'LEGACY',
                'class': strategy_class.__name__,
                'instance': False,
            }
            for name, strategy_class in cls._legacy_strategies.items()
        ])
        
        return result


def register_default_strategies():
    """Register built-in strategies at startup (old + new)"""
    
    # ========== LEGACY OPTION STRATEGIES ==========
    try:
        from app.core.strategies.option_spread_15m.engine import OptionSpread15m
        from app.core.strategies.option_spread_custom.engine import OptionSpreadCustom
        
        StrategyRegistry.register_legacy('option_spread_15m', OptionSpread15m)
        StrategyRegistry.register_legacy('option_spread_custom', OptionSpreadCustom)
        logger.info("✅ Legacy option strategies registered")
    except Exception as e:
        logger.warning(f"⚠️ Could not register legacy strategies: {e}")
    
    # ========== NEW STOCK STRATEGIES ==========
    try:
        from app.core.strategies.stock_strategies import (
            MomentumStrategy,
            MeanReversionStrategy,
            TrendFollowingStrategy,
        )
        
        # Register 15m timeframe strategies
        StrategyRegistry.register('stock_momentum_15m', MomentumStrategy())
        StrategyRegistry.register('stock_mean_reversion_15m', MeanReversionStrategy())
        StrategyRegistry.register('stock_trend_following_15m', TrendFollowingStrategy())
        
        # Register daily timeframe strategies (same classes, different registration)
        StrategyRegistry.register('stock_momentum_daily', MomentumStrategy())
        StrategyRegistry.register('stock_mean_reversion_daily', MeanReversionStrategy())
        StrategyRegistry.register('stock_trend_following_daily', TrendFollowingStrategy())
        
        logger.info("✅ New stock strategies registered (15m + daily)")
    except Exception as e:
        logger.warning(f"⚠️ Could not register stock strategies: {e}")
# Auto-register on import
try:
    register_default_strategies()
except Exception as e:
    logger.warning(f"⚠️ Could not auto-register strategies: {e}")
