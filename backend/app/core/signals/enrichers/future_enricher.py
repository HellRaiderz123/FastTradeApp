"""
future_enricher.py
------------------
Enriches signals for futures contracts with contract specs and basis context.

Adds:
- Contract specs: Multiplier, tick size, trading hours
- Basis analysis: Future - spot spread, basis trend
- Roll dates: Expiry schedule, roll recommendations
- Open interest: Contract liquidity, commitment of traders
- Leverage context: Implied leverage, margin required
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.core.signals.base import Signal, SignalEnricher, AssetType

logger = logging.getLogger(__name__)


class FutureEnricher(SignalEnricher):
    """Enrich future signals with contract and basis context"""
    
    def __init__(self):
        super().__init__(AssetType.FUTURE)
    
    def enrich(self, signal: Signal) -> Signal:
        """
        Enrich future signal with contract specs and basis data.
        
        Ensures key future-specific fields are present in context.
        """
        if signal.asset_type != AssetType.FUTURE:
            return signal
        
        # Ensure future-specific context fields
        signal.context.setdefault("asset_type", "FUTURE")
        signal.context.setdefault("underlying", None)
        signal.context.setdefault("contract_month", None)
        signal.context.setdefault("expiry_date", None)
        signal.context.setdefault("days_to_expiry", None)
        
        # Contract specs
        signal.context.setdefault("multiplier", None)  # Per lot
        signal.context.setdefault("tick_size", None)
        signal.context.setdefault("lot_size", None)
        signal.context.setdefault("margin_required", None)
        signal.context.setdefault("trading_hours", None)
        
        # Basis analysis
        signal.context.setdefault("spot_price", None)
        signal.context.setdefault("future_price", None)
        signal.context.setdefault("basis", None)  # Future - spot
        signal.context.setdefault("basis_trend", None)  # Widening or narrowing
        signal.context.setdefault("cost_of_carry", None)  # Implied interest rate
        
        # Liquidity
        signal.context.setdefault("open_interest", None)
        signal.context.setdefault("volume", None)
        signal.context.setdefault("bid_ask_spread", None)
        
        # Roll info
        signal.context.setdefault("next_expiry", None)
        signal.context.setdefault("next_contract", None)
        signal.context.setdefault("roll_recommendation", None)
        
        # Leverage
        signal.context.setdefault("implied_leverage", None)  # 1:X
        signal.context.setdefault("margin_to_notional", None)  # %
        
        return signal
    
    def compute_quality_checks(self, signal: Signal) -> Signal:
        """
        Compute future-specific quality checks.
        
        Checks:
        - Liquidity: Is OI and volume sufficient?
        - Bid-Ask: Is spread reasonable?
        - Basis: Is basis reasonable (not anomalous)?
        - Expiry: Is contract not expiring very soon (min 7 DTE)?
        - Cost of Carry: Is basis consistent with interest rates?
        """
        if signal.asset_type != AssetType.FUTURE:
            return signal
        
        quality_checks = signal.quality_checks.copy()
        context = signal.context or {}
        
        # Liquidity check
        oi = context.get("open_interest", 0)
        volume = context.get("volume", 0)
        quality_checks["liquidity_ok"] = (oi and oi > 500) or (volume and volume > 50)
        
        # Bid-ask spread check (for futures, typically tighter than options)
        spread = context.get("bid_ask_spread", 0)
        quality_checks["spread_acceptable"] = spread is None or spread < 0.2  # <0.2% spread
        
        # Basis check (should not be wildly out of line)
        basis = context.get("basis")
        coc = context.get("cost_of_carry")
        if basis is not None and coc is not None:
            # Basis deviation from fair value should be < 2%
            basis_deviation = abs(basis - coc)
            quality_checks["basis_normal"] = basis_deviation < 2.0
        else:
            quality_checks["basis_normal"] = True
        
        # Expiry check (min 7 DTE for directional trades)
        dte = context.get("days_to_expiry")
        if dte:
            quality_checks["expiry_ok"] = dte >= 7 and dte < 365
        else:
            quality_checks["expiry_ok"] = True
        
        # Margin constraint check (should not require >50% margin to trade)
        margin_pct = context.get("margin_to_notional")
        if margin_pct:
            quality_checks["margin_ok"] = margin_pct < 50
        else:
            quality_checks["margin_ok"] = True
        
        # Basis trend check (widening basis may indicate roll opportunity)
        basis_trend = context.get("basis_trend")
        if basis_trend and signal.signal.value == "HOLD":
            # If basis is narrowing significantly, hold until next contract
            quality_checks["roll_ok"] = basis_trend != "NARROWING_FAST"
        else:
            quality_checks["roll_ok"] = True
        
        # Recalculate quality score
        quality_score = sum(1 for v in quality_checks.values() if v)
        
        signal.quality_checks = quality_checks
        signal.quality_score = quality_score
        
        return signal
