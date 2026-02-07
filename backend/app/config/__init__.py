"""
Configuration package for FastTradeApp.
Contains market symbols, scanner strategies, and trading parameters.
"""

from .market_config import (
    MarketUniverse,
    TradingStyle,
    MARKET_SYMBOLS,
    SCANNER_STRATEGIES,
    SECTOR_CLASSIFICATION,
    INDICATOR_DEFAULTS,
    get_symbols,
    get_scanner_strategies,
    get_strategy_by_style,
    get_sector_symbols,
    get_all_sectors,
)

__all__ = [
    "MarketUniverse",
    "TradingStyle",
    "MARKET_SYMBOLS",
    "SCANNER_STRATEGIES",
    "SECTOR_CLASSIFICATION",
    "INDICATOR_DEFAULTS",
    "get_symbols",
    "get_scanner_strategies",
    "get_strategy_by_style",
    "get_sector_symbols",
    "get_all_sectors",
]
