"""
base_strategy.py
----------------
Base class for all trading strategies (stocks, options, futures, indices).

Provides:
- StrategyType enum: DIRECTIONAL, SPREAD, ARBITRAGE, HEDGING, RELATIVE
- BaseStrategy interface: Common methods for all strategy types
- StrategyResult: Standardized output format
- StrategyConfig: Database-agnostic strategy configuration
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from pydantic import BaseModel
from datetime import datetime

from app.core.signals.base import Signal, AssetType
from app.core.utils.time import now_ist


class StrategyType(str, Enum):
    """Strategy classification by pattern/logic"""
    DIRECTIONAL = "DIRECTIONAL"  # Buy/sell based on trend
    SPREAD = "SPREAD"            # Multi-leg option spreads
    ARBITRAGE = "ARBITRAGE"      # Cash and carry, calendar spreads
    HEDGING = "HEDGING"          # Protective calls, collars
    RELATIVE = "RELATIVE"        # Calendar spreads, butterflies
    MOMENTUM = "MOMENTUM"        # Momentum-based stock trades
    MEAN_REVERSION = "MEAN_REVERSION"  # Support/resistance bounces
    COVERED = "COVERED"          # Covered calls, protective puts


class StrategyLeg(BaseModel):
    """Single leg of a multi-leg strategy"""
    symbol: str
    action: str  # BUY, SELL
    quantity: int
    entry_price: float
    exit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    pnl: Optional[float] = None
    status: str = "PENDING"  # PENDING, EXECUTED, CLOSED


class StrategyResult(BaseModel):
    """
    Standardized output from strategy evaluation.
    
    Contains:
    - recommendation: BUY, SELL, HOLD, NO_TRADE
    - confidence: 0-100%
    - entry, exit, stop levels
    - risk metrics (max loss, Greeks, margin)
    - legs (for multi-leg strategies)
    - reasoning
    """
    
    strategy_name: str
    strategy_type: StrategyType
    asset_types: List[AssetType]  # Can be multi-asset (e.g., [STOCK, OPTION])
    symbol: str
    
    recommendation: str  # BUY, SELL, HOLD, NO_TRADE
    confidence: float  # 0-100
    reasoning: str
    
    # Entry/exit levels
    entry_price: float
    entry_quantity: int
    target_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    
    # Risk metrics
    max_profit: Optional[float] = None
    max_loss: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    margin_required: Optional[float] = None
    
    # Greeks (for option strategies)
    greeks: Dict[str, float] = {}  # delta, gamma, theta, vega, rho
    
    # Multi-leg details
    legs: List[StrategyLeg] = []
    
    # Quality metrics
    quality_score: int  # 0-10
    trade_readiness_score: int  # 0-100
    
    # Context
    signal: Optional[Dict] = None
    context: Dict[str, Any] = {}
    
    timestamp: datetime = None  # Will use IST on creation


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    
    Subclasses must implement:
    - initialize(): Setup strategy configuration
    - evaluate_signal(): Check if signal is actionable
    - generate_legs(): Create multi-leg structure if needed
    - calculate_risk(): Compute Greeks, margin, stop/target
    - prepare_result(): Format final StrategyResult
    """
    
    def __init__(self, name: str, strategy_type: StrategyType, asset_types: List[AssetType]):
        self.name = name
        self.strategy_type = strategy_type
        self.asset_types = asset_types
        self.config: Dict[str, Any] = {}
        self.legs: List[StrategyLeg] = []
    
    def set_config(self, config: Dict[str, Any]) -> None:
        """Set strategy configuration from database or user input"""
        self.config = config
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize strategy with config.
        Returns True if config is valid, else False.
        """
        pass
    
    @abstractmethod
    def evaluate_signal(self, signal: Signal) -> bool:
        """
        Evaluate if signal meets strategy requirements.
        Returns True if signal is actionable for this strategy.
        
        Example: OptionSpread requires confidence > 60 and IV regime compatible
        """
        pass
    
    @abstractmethod
    def generate_legs(self, signal: Signal, **kwargs) -> List[StrategyLeg]:
        """
        Generate multi-leg structure from signal.
        Single-leg strategies return 1 leg; spreads return 3-5.
        """
        pass
    
    @abstractmethod
    def calculate_risk(self, legs: List[StrategyLeg]) -> Dict[str, Any]:
        """
        Calculate risk metrics: Greeks, max profit/loss, margin, etc.
        Returns dict with all risk metrics.
        """
        pass
    
    @abstractmethod
    def validate_risk(self, risk_metrics: Dict[str, Any]) -> bool:
        """
        Validate risk against limits.
        Returns True if risk is within acceptable bounds.
        """
        pass
    
    def evaluate_and_generate(
        self,
        signal: Signal,
        market_data: Dict[str, Any] = None,
        **kwargs
    ) -> Optional[StrategyResult]:
        """
        Complete flow: signal → legs → risk → result.
        
        Returns StrategyResult if strategy is executable, else None.
        """
        # 1. Check if signal is actionable
        if not self.evaluate_signal(signal):
            return None  # Signal doesn't meet criteria
        
        # 2. Generate legs
        legs = self.generate_legs(signal, **kwargs)
        if not legs:
            return None
        
        self.legs = legs
        
        # 3. Calculate risk
        risk_metrics = self.calculate_risk(legs)
        
        # 4. Validate risk
        if not self.validate_risk(risk_metrics):
            return None  # Risk exceeds limits
        
        # 5. Prepare result
        result = self.prepare_result(signal, legs, risk_metrics)
        return result
    
    def prepare_result(
        self,
        signal: Signal,
        legs: List[StrategyLeg],
        risk_metrics: Dict[str, Any]
    ) -> StrategyResult:
        """
        Format final StrategyResult from signal, legs, and risk.
        Can be overridden for custom formatting.
        """
        primary_leg = legs[0] if legs else StrategyLeg(
            symbol=signal.symbol,
            action="BUY",
            quantity=1,
            entry_price=0
        )
        
        return StrategyResult(
            strategy_name=self.name,
            strategy_type=self.strategy_type,
            asset_types=self.asset_types,
            symbol=signal.symbol,
            recommendation=signal.signal.value,
            confidence=signal.confidence,
            reasoning=signal.reasoning,
            entry_price=primary_leg.entry_price,
            entry_quantity=primary_leg.quantity,
            target_price=risk_metrics.get("target"),
            stop_loss_price=risk_metrics.get("stop_loss"),
            max_profit=risk_metrics.get("max_profit"),
            max_loss=risk_metrics.get("max_loss"),
            risk_reward_ratio=risk_metrics.get("risk_reward_ratio"),
            margin_required=risk_metrics.get("margin_required"),
            greeks=risk_metrics.get("greeks", {}),
            legs=legs,
            quality_score=signal.quality_score,
            trade_readiness_score=signal.trade_readiness_score,
            signal=signal.dict(exclude_unset=True),
            context=signal.context,
            timestamp=now_ist(),
        )
    
    def __repr__(self) -> str:
        return f"<{self.name} ({self.strategy_type.value})>"
