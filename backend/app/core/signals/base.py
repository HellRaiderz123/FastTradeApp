"""
base.py
-------
Base classes for multi-asset signal generation.

Provides:
- AssetType enum: STOCK, OPTION, FUTURE, INDEX
- Signal base class: Common structure for all asset types
- SignalFactory: Creates asset-specific signals
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel


class AssetType(str, Enum):
    """Asset type classification"""
    STOCK = "STOCK"
    OPTION = "OPTION"
    FUTURE = "FUTURE"
    INDEX = "INDEX"


class SignalStrength(str, Enum):
    """Signal strength levels"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    NO_TRADE = "NO_TRADE"


class MarketBias(str, Enum):
    """Market direction bias"""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class IVRegime(str, Enum):
    """Implied volatility regime"""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


class Signal(BaseModel):
    """
    Standard signal format for all asset types.
    
    Fields:
    - asset_type: STOCK, OPTION, FUTURE, INDEX
    - symbol: Trading symbol (e.g., "RELIANCE", "NIFTY50", "BANKNIFTY24FEB10400CE")
    - timestamp: When signal was generated
    - signal: BUY, SELL, HOLD, NO_TRADE
    - confidence: 0-100, higher = more certain
    - bias: BULLISH, BEARISH, NEUTRAL (market direction)
    - indicators: Dict of all computed indicators (RSI, MA, IV, Greeks, etc.)
    - context: Market context (VIX, IV regime, market cap, sector, etc.)
    - quality_checks: Dict of bool checks that passed (e.g., volume_ok, rsi_extreme, etc.)
    - quality_score: Count of passed checks
    - trade_readiness_score: 0-100 for position sizing and risk adjustments
    - reasoning: Human-readable explanation
    """
    
    # Core signal info
    asset_type: AssetType
    symbol: str
    timestamp: datetime
    
    # Signal output
    signal: SignalStrength
    confidence: float  # 0-100
    bias: MarketBias
    reasoning: str
    
    # Market context
    iv_regime: Optional[IVRegime] = None
    india_vix: Optional[float] = None
    vix_rank: Optional[float] = None
    
    # Technical/fundamental data
    indicators: Dict[str, Any] = {}
    context: Dict[str, Any] = {}
    
    # Quality assessment
    quality_checks: Dict[str, bool] = {}
    quality_score: int = 0
    trade_readiness_score: int = 0  # 0-100
    
    class Config:
        use_enum_values = False


class SignalEnricher:
    """Base class for asset-specific signal enrichment"""
    
    def __init__(self, asset_type: AssetType):
        self.asset_type = asset_type
    
    def enrich(self, signal: Signal) -> Signal:
        """
        Enrich base signal with asset-specific fields.
        
        Override in subclasses to add:
        - Greeks (for options)
        - Fundamentals (for stocks)
        - Contract info (for futures)
        - Constituent info (for indices)
        """
        return signal
    
    def compute_quality_checks(self, signal: Signal) -> Signal:
        """
        Compute asset-specific quality checks.
        Override in subclasses for custom validation.
        """
        return signal


class SignalFactory:
    """Factory for creating asset-specific signals"""
    
    _enrichers: Dict[AssetType, SignalEnricher] = {}
    
    @classmethod
    def register_enricher(cls, asset_type: AssetType, enricher: SignalEnricher) -> None:
        """Register an enricher for asset type"""
        cls._enrichers[asset_type] = enricher
    
    @classmethod
    def create_signal(
        cls,
        asset_type: AssetType,
        symbol: str,
        signal_strength: SignalStrength,
        confidence: float,
        bias: MarketBias,
        reasoning: str,
        indicators: Dict[str, Any] = None,
        context: Dict[str, Any] = None,
        **kwargs
    ) -> Signal:
        """Create and enrich a signal for the given asset type"""
        
        signal = Signal(
            asset_type=asset_type,
            symbol=symbol,
            timestamp=datetime.utcnow(),
            signal=signal_strength,
            confidence=min(100, max(0, confidence)),  # Clamp 0-100
            bias=bias,
            reasoning=reasoning,
            indicators=indicators or {},
            context=context or {},
            **kwargs
        )
        
        # Apply asset-specific enrichment
        if asset_type in cls._enrichers:
            enricher = cls._enrichers[asset_type]
            signal = enricher.enrich(signal)
            signal = enricher.compute_quality_checks(signal)
        
        return signal
    
    @classmethod
    def list_enrichers(cls) -> List[AssetType]:
        """List registered enrichers"""
        return list(cls._enrichers.keys())
