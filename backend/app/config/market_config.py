"""
Market Configuration
Centralized configuration for symbols, strategies, and market settings
"""

from typing import Dict, List
from enum import Enum


# Market Indices and Universes
class MarketUniverse(str, Enum):
    """Available market universes for analysis"""
    NIFTY50 = "NIFTY50"
    NIFTY100 = "NIFTY100"
    NIFTY500 = "NIFTY500"
    BANKNIFTY = "BANKNIFTY"
    FINNIFTY = "FINNIFTY"
    NIFTY_IT = "NIFTY_IT"
    CUSTOM = "CUSTOM"


# Symbol Lists (can be loaded from database or external source)
MARKET_SYMBOLS = {
    "NIFTY50": [
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
        "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "BAJFINANCE",
        "KOTAKBANK", "LT", "AXISBANK", "ASIANPAINT", "MARUTI",
        "TITAN", "SUNPHARMA", "ULTRACEMCO", "NESTLEIND", "WIPRO",
        "HCLTECH", "BAJAJFINSV", "NTPC", "ONGC", "POWERGRID",
        "M&M", "TECHM", "ADANIGREEN", "TATAMOTORS", "TATASTEEL",
        "INDUSINDBK", "DRREDDY", "APOLLOHOSP", "DIVISLAB", "CIPLA",
        "EICHERMOT", "BRITANNIA", "HEROMOTOCO", "GRASIM", "JSWSTEEL",
        "TATACONSUM", "HINDALCO", "COALINDIA", "SBILIFE", "BAJAJ-AUTO",
        "ADANIPORTS", "BPCL", "SHREECEM", "HDFCLIFE", "UPL"
    ],
    "BANKNIFTY": [
        "HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK",
        "INDUSINDBK", "BANDHANBNK", "FEDERALBNK", "IDFCFIRSTB", "PNB",
        "BANKBARODA", "AUBANK"
    ],
    "NIFTY_IT": [
        "TCS", "INFY", "WIPRO", "HCLTECH", "TECHM",
        "LTIM", "COFORGE", "PERSISTENT", "MPHASIS"
    ],
    "FINNIFTY": [
        "HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK",
        "BAJFINANCE", "BAJAJFINSV", "HDFCLIFE", "SBILIFE", "ICICIGI",
        "BAJAJHLDNG", "PFC", "RECLTD", "MUTHOOTFIN", "CHOLAFIN"
    ],
}

# Trading Styles Configuration
class TradingStyle(str, Enum):
    """Trading timeframe styles"""
    SCALPING = "scalping"  # Minutes
    INTRADAY = "intraday"  # Same day
    SWING = "swing"        # Days to weeks
    POSITIONAL = "positional"  # Weeks to months


# Scanner Strategy Definitions
SCANNER_STRATEGIES = {
    "momentum_breakout": {
        "name": "Momentum Breakout",
        "description": "Strong uptrend with high momentum and volume confirmation",
        "criteria": "ADX > 25, +DI > -DI, Volume > 1.5x average, RSI > 50",
        "ideal_for": TradingStyle.SWING,
        "timeframe": "3-7 days",
        "risk_level": "Medium",
        "min_adx": 25,
        "min_rsi": 50,
        "volume_threshold": 1.5
    },
    "oversold_bounce": {
        "name": "Oversold Bounce",
        "description": "Oversold conditions with reversal signals",
        "criteria": "RSI < 35, MACD crossover bullish, Price near lower Bollinger Band",
        "ideal_for": TradingStyle.SWING,
        "timeframe": "2-5 days",
        "risk_level": "Medium-High",
        "max_rsi": 35,
        "require_macd_cross": True
    },
    "trend_following": {
        "name": "Trend Following",
        "description": "Stable trends suitable for position trades",
        "criteria": "ADX > 25, Consistent directional movement",
        "ideal_for": TradingStyle.POSITIONAL,
        "timeframe": "1-4 weeks",
        "risk_level": "Low-Medium",
        "min_adx": 25
    },
    "volume_surge": {
        "name": "Volume Surge",
        "description": "Unusual volume activity indicating institutional interest",
        "criteria": "Volume > 2x average, Price breakout",
        "ideal_for": TradingStyle.INTRADAY,
        "timeframe": "Same day",
        "risk_level": "High",
        "volume_threshold": 2.0
    },
    "bollinger_squeeze": {
        "name": "Bollinger Squeeze",
        "description": "Low volatility compression before breakout",
        "criteria": "Narrow Bollinger Bands, Low ATR, Followed by expansion",
        "ideal_for": TradingStyle.SWING,
        "timeframe": "3-10 days",
        "risk_level": "Medium",
        "bandwidth_threshold": 10
    },
    "rsi_divergence": {
        "name": "RSI Divergence",
        "description": "Price and RSI moving in opposite directions",
        "criteria": "Price making lower lows while RSI making higher lows (bullish divergence)",
        "ideal_for": TradingStyle.SWING,
        "timeframe": "3-7 days",
        "risk_level": "Medium"
    }
}

# Sector Classifications
SECTOR_CLASSIFICATION = {
    "Banking & Finance": ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK", "BAJFINANCE", "BAJAJFINSV"],
    "IT": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM"],
    "Auto": ["MARUTI", "TATAMOTORS", "EICHERMOT", "HEROMOTOCO", "BAJAJ-AUTO", "M&M"],
    "Pharma": ["SUNPHARMA", "DRREDDY", "APOLLOHOSP", "DIVISLAB", "CIPLA"],
    "Energy": ["RELIANCE", "ONGC", "NTPC", "POWERGRID", "BPCL", "COALINDIA"],
    "FMCG": ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "TATACONSUM"],
    "Metals": ["TATASTEEL", "JSWSTEEL", "HINDALCO"],
    "Cement": ["ULTRACEMCO", "SHREECEM", "GRASIM"]
}

# Technical Indicator Defaults
INDICATOR_DEFAULTS = {
    "rsi": {"period": 14, "overbought": 70, "oversold": 30},
    "macd": {"fast": 12, "slow": 26, "signal": 9},
    "bollinger": {"period": 20, "std_dev": 2.0},
    "adx": {"period": 14, "trend_threshold": 25},
    "sma": {"short": 20, "medium": 50, "long": 200},
    "ema": {"short": 12, "long": 26},
    "stochastic": {"k_period": 14, "d_period": 3, "overbought": 80, "oversold": 20},
    "atr": {"period": 14}
}


def get_symbols(universe: str = "NIFTY50") -> List[str]:
    """Get symbol list for a market universe"""
    return MARKET_SYMBOLS.get(universe, MARKET_SYMBOLS["NIFTY50"])


def get_scanner_strategies() -> Dict:
    """Get all available scanner strategies"""
    return SCANNER_STRATEGIES


def get_strategy_by_style(trading_style: TradingStyle) -> List[Dict]:
    """Get strategies filtered by trading style"""
    return [
        {**strategy, "id": key}
        for key, strategy in SCANNER_STRATEGIES.items()
        if strategy.get("ideal_for") == trading_style
    ]


def get_sector_symbols(sector: str) -> List[str]:
    """Get stocks in a specific sector"""
    return SECTOR_CLASSIFICATION.get(sector, [])


def get_all_sectors() -> List[str]:
    """Get list of all sectors"""
    return list(SECTOR_CLASSIFICATION.keys())
