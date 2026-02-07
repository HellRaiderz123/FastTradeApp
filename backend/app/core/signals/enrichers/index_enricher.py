"""
index_enricher.py
-----------------
Enriches signals for indices (NIFTY 50, BANKNIFTY, etc.) with constituent analysis.

Adds:
- Constituent performance: Which stocks driving the index
- Breadth analysis: Advance/decline ratio, percentage of stocks above MA
- Market cap concentration: Weight of top 5, top 10 stocks
- Sector contribution: Which sectors contributing to index move
- Index-specific data: Index PE, dividend yield, relative strength
"""

import logging
from typing import Dict, Any, Optional, List

from app.core.signals.base import Signal, SignalEnricher, AssetType

logger = logging.getLogger(__name__)


class IndexEnricher(SignalEnricher):
    """Enrich index signals with constituent and breadth analysis"""
    
    def __init__(self):
        super().__init__(AssetType.INDEX)
    
    def enrich(self, signal: Signal) -> Signal:
        """
        Enrich index signal with constituent and aggregated analysis.
        
        Ensures key index-specific fields are present in context.
        """
        if signal.asset_type != AssetType.INDEX:
            return signal
        
        # Ensure index-specific context fields
        signal.context.setdefault("asset_type", "INDEX")
        
        # Index composition
        signal.context.setdefault("index_name", None)
        signal.context.setdefault("num_constituents", None)  # 50, 20, etc.
        signal.context.setdefault("constituents", [])  # List of stocks in index
        
        # Breadth metrics
        signal.context.setdefault("advances", 0)  # Num stocks above open
        signal.context.setdefault("declines", 0)  # Num stocks below open
        signal.context.setdefault("advances_percent", 0)  # % advancing
        signal.context.setdefault("declines_percent", 0)  # % declining
        signal.context.setdefault("breadth_ratio", None)  # Advances / declines
        
        # Constituent performance
        signal.context.setdefault("top_gainers", [])  # List of top 5 gainers
        signal.context.setdefault("top_losers", [])   # List of top 5 losers
        signal.context.setdefault("largest_contributors", [])  # Stocks with largest impact
        
        # Market cap concentration
        signal.context.setdefault("top5_weight", None)  # Weight of top 5 stocks
        signal.context.setdefault("top10_weight", None)  # Weight of top 10 stocks
        signal.context.setdefault("dispersion", None)  # Concentration metric (0-100)
        
        # Sector contribution
        signal.context.setdefault("sector_contribution", {})  # {sector: contribution_pct}
        signal.context.setdefault("leading_sectors", [])  # Sectors driving index up
        signal.context.setdefault("lagging_sectors", [])  # Sectors dragging index down
        
        # Index valuation and relative strength
        signal.context.setdefault("index_pe", None)
        signal.context.setdefault("index_dividend_yield", None)
        signal.context.setdefault("relative_strength_vs_nifty", None)  # For BANKNIFTY vs NIFTY50
        
        return signal
    
    def compute_quality_checks(self, signal: Signal) -> Signal:
        """
        Compute index-specific quality checks.
        
        Checks:
        - Breadth confirmation: Is signal confirmed by majority of stocks?
        - Concentration: Is move driven by few or well-diversified?
        - Sector alignment: Are sectors aligned with index direction?
        - Trend confirmation: Do top gainers align with signal?
        """
        if signal.asset_type != AssetType.INDEX:
            return signal
        
        quality_checks = signal.quality_checks.copy()
        context = signal.context or {}
        
        # Breadth confirmation
        advances_pct = context.get("advances_percent", 0)
        declines_pct = context.get("declines_percent", 0)
        
        if signal.bias.value == "BULLISH":
            # For bullish move, expect >60% stocks advancing
            quality_checks["breadth_confirmation"] = advances_pct > 60
        elif signal.bias.value == "BEARISH":
            # For bearish move, expect >60% stocks declining
            quality_checks["breadth_confirmation"] = declines_pct > 60
        else:
            quality_checks["breadth_confirmation"] = True
        
        # Concentration assessment
        top5_weight = context.get("top5_weight")
        if top5_weight:
            # If top 5 > 30%, move is concentrated; < 20% is well-distributed
            is_concentrated = top5_weight > 30
            # For trend confirmation, prefer distributed moves (less manipulable)
            quality_checks["distribution_ok"] = not is_concentrated or advances_pct > 70
        else:
            quality_checks["distribution_ok"] = True
        
        # Sector alignment
        leading_sectors = context.get("leading_sectors", [])
        lagging_sectors = context.get("lagging_sectors", [])
        
        if signal.bias.value == "BULLISH":
            # Expect >3 leading sectors (not just IT/Financials)
            quality_checks["sector_alignment"] = len(leading_sectors) >= 3
        elif signal.bias.value == "BEARISH":
            # Expect >3 lagging sectors
            quality_checks["sector_alignment"] = len(lagging_sectors) >= 3
        else:
            quality_checks["sector_alignment"] = True
        
        # Trend confirmation by large movers
        largest_contributors = context.get("largest_contributors", [])
        if largest_contributors:
            # Check if majority of large movers align with signal direction
            aligned = sum(
                1 for contrib in largest_contributors[:5]
                if (signal.bias.value == "BULLISH" and contrib.get("change", 0) > 0) or
                   (signal.bias.value == "BEARISH" and contrib.get("change", 0) < 0)
            )
            quality_checks["mover_alignment"] = aligned >= 3  # At least 3 of top 5 aligned
        else:
            quality_checks["mover_alignment"] = True
        
        # Pattern strength (breadth ratio)
        breadth_ratio = context.get("breadth_ratio")
        if breadth_ratio:
            # Healthy breadth ratio is 1.5-2.0
            quality_checks["breadth_strength"] = 1.2 < breadth_ratio < 3.0
        else:
            quality_checks["breadth_strength"] = True
        
        # Recalculate quality score
        quality_score = sum(1 for v in quality_checks.values() if v)
        
        signal.quality_checks = quality_checks
        signal.quality_score = quality_score
        
        return signal
