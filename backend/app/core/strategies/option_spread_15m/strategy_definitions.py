"""
Strategy Definitions and Requirements
--------------------------------------
Comprehensive list of all supported option strategies with their characteristics.
"""

from enum import Enum
from typing import Dict, List, Tuple
from dataclasses import dataclass


class StrategyType(str, Enum):
    """All supported strategy types"""
    
    # Credit Spreads (sell premium, limited risk/reward)
    BULL_PUT = "BULL_PUT"
    BEAR_CALL = "BEAR_CALL"
    IRON_CONDOR = "IRON_CONDOR"
    
    # Debit Spreads (buy premium, limited risk/reward)
    BULL_CALL = "BULL_CALL"
    BEAR_PUT = "BEAR_PUT"
    
    # Straddles & Strangles
    SHORT_STRADDLE = "SHORT_STRADDLE"
    LONG_STRADDLE = "LONG_STRADDLE"
    SHORT_STRANGLE = "SHORT_STRANGLE"
    LONG_STRANGLE = "LONG_STRANGLE"
    
    # Advanced
    BUTTERFLY_SPREAD = "BUTTERFLY_SPREAD"       # Call or Put Butterfly
    CALL_RATIO_BACKSPREAD = "CALL_RATIO_BACKSPREAD"   # 1 short ITM, 2+ long OTM
    PUT_RATIO_BACKSPREAD = "PUT_RATIO_BACKSPREAD"     # 1 short ITM, 2+ long OTM
    
    # Special
    NO_TRADE = "NO_TRADE"


@dataclass
class StrategyCharacteristics:
    """Define characteristics of each strategy"""
    name: str
    bias: str                    # BULLISH, BEARISH, NEUTRAL
    risk_profile: str            # LIMITED_RISK, UNLIMITED_RISK
    market_condition: str        # TRENDING, RANGE, BREAKOUT, VOLATILE
    iv_regime: str               # LOW, NORMAL, HIGH, ANY
    min_quality_score: int       # 0-8
    min_confidence: float        # 0-100
    num_legs: int
    margin_type: str             # CREDIT, DEBIT, SPREAD
    complexity: str              # SIMPLE, MEDIUM, ADVANCED
    max_profit: str              # LIMITED, UNLIMITED, description
    max_loss: str                # LIMITED, UNLIMITED, description
    breakeven_count: int         # Number of breakeven points


# Strategy definitions
STRATEGY_CONFIGS: Dict[StrategyType, StrategyCharacteristics] = {
    
    # ========== CREDIT SPREADS ==========
    StrategyType.BULL_PUT: StrategyCharacteristics(
        name="Bull Put Spread",
        bias="BULLISH",
        risk_profile="LIMITED_RISK",
        market_condition="RANGE",
        iv_regime="NORMAL",
        min_quality_score=4,
        min_confidence=60,
        num_legs=2,
        margin_type="CREDIT",
        complexity="SIMPLE",
        max_profit="Premium received",
        max_loss="Spread width - Premium",
        breakeven_count=1,
    ),
    
    StrategyType.BEAR_CALL: StrategyCharacteristics(
        name="Bear Call Spread",
        bias="BEARISH",
        risk_profile="LIMITED_RISK",
        market_condition="RANGE",
        iv_regime="NORMAL",
        min_quality_score=4,
        min_confidence=60,
        num_legs=2,
        margin_type="CREDIT",
        complexity="SIMPLE",
        max_profit="Premium received",
        max_loss="Spread width - Premium",
        breakeven_count=1,
    ),
    
    StrategyType.IRON_CONDOR: StrategyCharacteristics(
        name="Iron Condor",
        bias="NEUTRAL",
        risk_profile="LIMITED_RISK",
        market_condition="RANGE",
        iv_regime="HIGH",
        min_quality_score=5,
        min_confidence=70,
        num_legs=4,
        margin_type="CREDIT",
        complexity="MEDIUM",
        max_profit="Total premium received",
        max_loss="Spread width - Premium",
        breakeven_count=2,
    ),
    
    # ========== DEBIT SPREADS ==========
    StrategyType.BULL_CALL: StrategyCharacteristics(
        name="Bull Call Spread",
        bias="BULLISH",
        risk_profile="LIMITED_RISK",
        market_condition="TRENDING",
        iv_regime="LOW",
        min_quality_score=5,
        min_confidence=65,
        num_legs=2,
        margin_type="DEBIT",
        complexity="SIMPLE",
        max_profit="Spread width - Premium paid",
        max_loss="Premium paid",
        breakeven_count=1,
    ),
    
    StrategyType.BEAR_PUT: StrategyCharacteristics(
        name="Bear Put Spread",
        bias="BEARISH",
        risk_profile="LIMITED_RISK",
        market_condition="TRENDING",
        iv_regime="LOW",
        min_quality_score=5,
        min_confidence=65,
        num_legs=2,
        margin_type="DEBIT",
        complexity="SIMPLE",
        max_profit="Spread width - Premium paid",
        max_loss="Premium paid",
        breakeven_count=1,
    ),
    
    # ========== STRADDLES ==========
    StrategyType.SHORT_STRADDLE: StrategyCharacteristics(
        name="Short Straddle",
        bias="NEUTRAL",
        risk_profile="UNLIMITED_RISK",
        market_condition="RANGE",
        iv_regime="HIGH",
        min_quality_score=6,
        min_confidence=75,
        num_legs=2,
        margin_type="CREDIT",
        complexity="MEDIUM",
        max_profit="Total premium received",
        max_loss="Unlimited both sides",
        breakeven_count=2,
    ),
    
    StrategyType.LONG_STRADDLE: StrategyCharacteristics(
        name="Long Straddle",
        bias="NEUTRAL",
        risk_profile="LIMITED_RISK",
        market_condition="VOLATILE",
        iv_regime="LOW",
        min_quality_score=5,
        min_confidence=70,
        num_legs=2,
        margin_type="DEBIT",
        complexity="MEDIUM",
        max_profit="Unlimited both sides",
        max_loss="Total premium paid",
        breakeven_count=2,
    ),
    
    # ========== STRANGLES ==========
    StrategyType.SHORT_STRANGLE: StrategyCharacteristics(
        name="Short Strangle",
        bias="NEUTRAL",
        risk_profile="UNLIMITED_RISK",
        market_condition="RANGE",
        iv_regime="HIGH",
        min_quality_score=6,
        min_confidence=75,
        num_legs=2,
        margin_type="CREDIT",
        complexity="MEDIUM",
        max_profit="Total premium received",
        max_loss="Unlimited both sides",
        breakeven_count=2,
    ),
    
    StrategyType.LONG_STRANGLE: StrategyCharacteristics(
        name="Long Strangle",
        bias="NEUTRAL",
        risk_profile="LIMITED_RISK",
        market_condition="VOLATILE",
        iv_regime="LOW",
        min_quality_score=5,
        min_confidence=70,
        num_legs=2,
        margin_type="DEBIT",
        complexity="MEDIUM",
        max_profit="Unlimited both sides",
        max_loss="Total premium paid",
        breakeven_count=2,
    ),
    
    # ========== ADVANCED ==========
    StrategyType.BUTTERFLY_SPREAD: StrategyCharacteristics(
        name="Butterfly Spread",
        bias="NEUTRAL",
        risk_profile="LIMITED_RISK",
        market_condition="RANGE",
        iv_regime="NORMAL",
        min_quality_score=5,
        min_confidence=70,
        num_legs=4,
        margin_type="DEBIT",
        complexity="ADVANCED",
        max_profit="Spread width - Premium paid",
        max_loss="Premium paid",
        breakeven_count=2,
    ),
    
    StrategyType.CALL_RATIO_BACKSPREAD: StrategyCharacteristics(
        name="Call Ratio Backspread",
        bias="BULLISH",
        risk_profile="LIMITED_RISK",
        market_condition="BREAKOUT",
        iv_regime="LOW",
        min_quality_score=6,
        min_confidence=75,
        num_legs=3,
        margin_type="CREDIT",
        complexity="ADVANCED",
        max_profit="Unlimited upside",
        max_loss="Limited (between strikes)",
        breakeven_count=2,
    ),
    
    StrategyType.PUT_RATIO_BACKSPREAD: StrategyCharacteristics(
        name="Put Ratio Backspread",
        bias="BEARISH",
        risk_profile="LIMITED_RISK",
        market_condition="BREAKOUT",
        iv_regime="LOW",
        min_quality_score=6,
        min_confidence=75,
        num_legs=3,
        margin_type="CREDIT",
        complexity="ADVANCED",
        max_profit="Unlimited downside",
        max_loss="Limited (between strikes)",
        breakeven_count=2,
    ),
}


def get_strategy_requirements(strategy: StrategyType) -> StrategyCharacteristics:
    """Get requirements for a specific strategy"""
    return STRATEGY_CONFIGS.get(strategy)


def get_strategies_for_conditions(
    bias: str,
    market_mode: str,
    iv_regime: str,
    quality_score: int,
    confidence: float,
) -> List[Tuple[StrategyType, StrategyCharacteristics]]:
    """Return all strategies that match current market conditions"""
    
    matching = []
    
    for strategy_type, config in STRATEGY_CONFIGS.items():
        if strategy_type == StrategyType.NO_TRADE:
            continue
            
        # Check if strategy matches conditions
        bias_match = config.bias == "NEUTRAL" or config.bias == bias
        market_match = config.market_condition == market_mode or market_mode == "ANY"
        iv_match = config.iv_regime == "ANY" or config.iv_regime == iv_regime
        quality_match = quality_score >= config.min_quality_score
        confidence_match = confidence >= config.min_confidence
        
        if bias_match and market_match and iv_match and quality_match and confidence_match:
            matching.append((strategy_type, config))
    
    return matching


def format_strategy_info(strategy: StrategyType) -> str:
    """Format strategy info for display"""
    config = STRATEGY_CONFIGS.get(strategy)
    if not config:
        return f"{strategy.value}"
    
    return f"""
{config.name}
Bias: {config.bias}
Market: {config.market_condition}
IV Regime: {config.iv_regime}
Legs: {config.num_legs}
Max Profit: {config.max_profit}
Max Loss: {config.max_loss}
Complexity: {config.complexity}
    """.strip()
