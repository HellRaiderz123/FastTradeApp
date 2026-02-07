"""
Market Configuration API
Endpoints to retrieve market symbols, strategies, and settings
"""

from fastapi import APIRouter
from typing import Dict, List
import logging

from app.config.market_config import (
    get_symbols,
    get_scanner_strategies,
    get_strategy_by_style,
    get_sector_symbols,
    get_all_sectors,
    MarketUniverse,
    TradingStyle,
    INDICATOR_DEFAULTS,
    SECTOR_CLASSIFICATION
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/config", tags=["configuration"])


@router.get("/market-universes")
async def get_market_universes() -> Dict[str, List[str]]:
    """
    Get all available market universes
    
    Returns:
        {
            "universes": ["NIFTY50", "NIFTY100", "BANKNIFTY"],
            "default": "NIFTY50"
        }
    """
    return {
        "universes": [u.value for u in MarketUniverse],
        "default": MarketUniverse.NIFTY50.value
    }


@router.get("/symbols/{universe}")
async def get_universe_symbols(universe: str = "NIFTY50") -> Dict[str, List[str]]:
    """
    Get symbol list for a specific market universe
    
    Args:
        universe: Market universe name (e.g., "NIFTY50", "BANKNIFTY")
    
    Returns:
        {
            "universe": "NIFTY50",
            "symbols": ["RELIANCE", "TCS", ...],
            "count": 50
        }
    """
    symbols = get_symbols(universe)
    return {
        "universe": universe,
        "symbols": symbols,
        "count": len(symbols)
    }


@router.get("/trading-styles")
async def get_trading_styles() -> Dict[str, List[Dict]]:
    """
    Get all available trading styles
    
    Returns:
        {
            "styles": [
                {"id": "scalping", "name": "Scalping", "timeframe": "Minutes"},
                {"id": "intraday", "name": "Intraday", "timeframe": "Same day"},
                ...
            ]
        }
    """
    styles = [
        {"id": TradingStyle.SCALPING.value, "name": "Scalping", "timeframe": "Minutes"},
        {"id": TradingStyle.INTRADAY.value, "name": "Intraday", "timeframe": "Same day"},
        {"id": TradingStyle.SWING.value, "name": "Swing", "timeframe": "Days to weeks"},
        {"id": TradingStyle.POSITIONAL.value, "name": "Positional", "timeframe": "Weeks to months"}
    ]
    return {"styles": styles}


@router.get("/scanner-strategies")
async def get_available_scanner_strategies(
    trading_style: str = None
) -> Dict[str, List[Dict]]:
    """
    Get all available scanner strategies, optionally filtered by trading style
    
    Args:
        trading_style: Filter by trading style (e.g., "swing", "intraday")
    
    Returns:
        {
            "strategies": [
                {
                    "id": "momentum_breakout",
                    "name": "Momentum Breakout",
                    "description": "...",
                    "ideal_for": "swing",
                    "risk_level": "Medium"
                },
                ...
            ],
            "count": 6
        }
    """
    strategies = get_scanner_strategies()
    
    # Convert to list format
    strategy_list = [
        {**strategy, "id": key}
        for key, strategy in strategies.items()
    ]
    
    # Filter by trading style if provided
    if trading_style:
        strategy_list = [
            s for s in strategy_list
            if s.get("ideal_for") == trading_style
        ]
    
    return {
        "strategies": strategy_list,
        "count": len(strategy_list)
    }


@router.get("/sectors")
async def get_sectors() -> Dict[str, List[str]]:
    """
    Get all sectors and their symbols
    
    Returns:
        {
            "sectors": {
                "Banking & Finance": ["HDFCBANK", "ICICIBANK", ...],
                "IT": ["TCS", "INFY", ...],
                ...
            },
            "sector_names": ["Banking & Finance", "IT", ...]
        }
    """
    return {
        "sectors": SECTOR_CLASSIFICATION,
        "sector_names": get_all_sectors()
    }


@router.get("/indicators")
async def get_indicator_defaults() -> Dict:
    """
    Get default parameters for technical indicators
    
    Returns:
        {
            "rsi": {"period": 14, "overbought": 70, "oversold": 30},
            "macd": {"fast": 12, "slow": 26, "signal": 9},
            ...
        }
    """
    return INDICATOR_DEFAULTS
