"""
option_enricher.py
------------------
Enriches signals for option strategies with Greeks, IV skew, and expiry context.

Adds:
- Greeks: Delta, gamma, theta, vega, rho
- IV context: IV level, IV skew, IV rank, IV percentile
- Open interest & volume: Liquidity indicators
- Expiry context: Days to expiry, expiry month, early assignment risk
- Spread-specific: Max profit, max loss, breakeven points
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.core.signals.base import Signal, SignalEnricher, AssetType

logger = logging.getLogger(__name__)


class OptionEnricher(SignalEnricher):
    """Enrich option signals with Greeks and volatility context"""
    
    def __init__(self):
        super().__init__(AssetType.OPTION)
    
    def enrich(self, signal: Signal) -> Signal:
        """
        Enrich option signal with Greeks and IV data.
        
        Ensures key option-specific fields are present in context.
        """
        if signal.asset_type != AssetType.OPTION:
            return signal
        
        # Ensure option-specific context fields
        signal.context.setdefault("asset_type", "OPTION")
        signal.context.setdefault("underlying", None)
        signal.context.setdefault("strike", None)
        signal.context.setdefault("option_type", None)  # CE or PE
        signal.context.setdefault("expiry_date", None)
        signal.context.setdefault("days_to_expiry", None)
        
        # Greeks
        signal.context.setdefault("delta", None)
        signal.context.setdefault("gamma", None)
        signal.context.setdefault("theta", None)
        signal.context.setdefault("vega", None)
        signal.context.setdefault("rho", None)
        
        # IV context
        signal.context.setdefault("iv_level", None)
        signal.context.setdefault("iv_percentile", None)
        signal.context.setdefault("iv_skew", None)  # Skew direction (ATM vs OTM)
        
        # Liquidity
        signal.context.setdefault("open_interest", None)
        signal.context.setdefault("volume", None)
        signal.context.setdefault("bid_ask_spread", None)
        
        # Spread-specific (if multi-leg)
        signal.context.setdefault("max_profit", None)
        signal.context.setdefault("max_loss", None)
        signal.context.setdefault("breakeven", None)
        signal.context.setdefault("roi_on_margin", None)
        
        return signal
    
    def compute_quality_checks(self, signal: Signal) -> Signal:
        """
        Compute option-specific quality checks.
        
        Checks:
        - Liquidity: Is OI and volume sufficient?
        - Bid-Ask: Is spread reasonable?
        - Expiry: Is expiry not too close (at least 3-5 DTE for spreads)?
        - Greeks: Are Greeks within acceptable range for strategy?
        - IV: Is IV rank above 30% (better premiums)?
        """
        if signal.asset_type != AssetType.OPTION:
            return signal
        
        quality_checks = signal.quality_checks.copy()
        context = signal.context or {}
        
        # Liquidity check
        oi = context.get("open_interest", 0)
        volume = context.get("volume", 0)
        quality_checks["liquidity_ok"] = (oi and oi > 100) or (volume and volume > 10)
        
        # Bid-ask spread check
        spread = context.get("bid_ask_spread", 0)
        quality_checks["spread_acceptable"] = spread is None or spread < 0.5  # <0.5% spread
        
        # Expiry check (need at least 3 DTE for spreads, 7+ for singles)
        dte = context.get("days_to_expiry")
        strategy_type = signal.context.get("strategy_type", "SINGLE")
        if dte:
            min_dte = 3 if strategy_type == "SPREAD" else 7
            quality_checks["expiry_ok"] = dte >= min_dte and dte < 60  # 60 DTE upper limit
        else:
            quality_checks["expiry_ok"] = True
        
        # IV percentile check (higher = better for premium sellers)
        iv_percentile = context.get("iv_percentile")
        if iv_percentile:
            quality_checks["iv_high_enough"] = iv_percentile >= 30  # At least 30th percentile
        else:
            quality_checks["iv_high_enough"] = True
        
        # Greeks reasonableness (strategy-dependent)
        delta = context.get("delta", 0)
        gamma = context.get("gamma", 0)
        vega = context.get("vega", 0)
        
        # For short spreads: want short gamma (profit from price movement)
        # For long spreads: want long gamma
        if signal.signal.value == "SELL":
            quality_checks["greeks_ok"] = gamma < 0.01 or gamma is None  # Short gamma
        elif signal.signal.value == "BUY":
            quality_checks["greeks_ok"] = gamma > 0 or gamma is None  # Long gamma
        else:
            quality_checks["greeks_ok"] = True
        
        # Recalculate quality score
        quality_score = sum(1 for v in quality_checks.values() if v)
        
        signal.quality_checks = quality_checks
        signal.quality_score = quality_score
        
        return signal
