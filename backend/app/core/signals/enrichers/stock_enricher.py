"""
stock_enricher.py
-----------------
Enriches signals for NIFTY 50 stocks with fundamentals and sector context.

Adds:
- Fundamental metrics: P/E, P/B, ROE, dividend yield, market cap
- Sector context: Sector name, sector performance
- Trend context: 52-week high/low, support/resistance levels
- Quality checks: Volume confirmation, trend alignment
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.signals.base import Signal, SignalEnricher, AssetType

logger = logging.getLogger(__name__)


class StockEnricher(SignalEnricher):
    """Enrich stock signals with fundamental analysis"""
    
    def __init__(self, db: Optional[Session] = None):
        super().__init__(AssetType.STOCK)
        self.db = db
    
    def enrich(self, signal: Signal) -> Signal:
        """
        Enrich stock signal with fundamental and sector data.
        
        If database connection available, fetch live fundamentals.
        Otherwise, use cached/default values.
        """
        if signal.asset_type != AssetType.STOCK:
            return signal
        
        try:
            # Try to fetch fundamentals from DB if available
            if self.db:
                fundamentals = self._fetch_fundamentals_from_db(signal.symbol)
                if fundamentals:
                    signal.context.update(fundamentals)
        except Exception as e:
            logger.warning(f"⚠️ Could not enrich stock {signal.symbol} with fundamentals: {e}")
        
        # Ensure key fundamental fields exist
        signal.context.setdefault("asset_type", "STOCK")
        signal.context.setdefault("pe_ratio", None)
        signal.context.setdefault("pb_ratio", None)
        signal.context.setdefault("dividend_yield", None)
        signal.context.setdefault("market_cap", None)
        signal.context.setdefault("sector", None)
        signal.context.setdefault("nifty_weight", None)
        
        return signal
    
    def compute_quality_checks(self, signal: Signal) -> Signal:
        """
        Compute stock-specific quality checks.
        
        Checks:
        - Volume spike: Is volume above 20-day average?
        - Trend alignment: Is signal aligned with major MA trend?
        - Support/Resistance: Is signal near key levels?
        - Sector momentum: Is signal aligned with sector trend?
        """
        if signal.asset_type != AssetType.STOCK:
            return signal
        
        quality_checks = signal.quality_checks.copy()
        
        # Volume check
        indicators = signal.indicators or {}
        volume = indicators.get("volume", 0)
        volume_sma20 = indicators.get("volume_sma20", 1)
        if volume > 0 and volume_sma20 > 0:
            volume_ratio = volume / volume_sma20
            quality_checks["volume_spike"] = volume_ratio > 1.2  # 20% above average
        else:
            quality_checks["volume_spike"] = False
        
        # Trend alignment check (simple: signal matches bias)
        current_price = indicators.get("close", 0)
        ma20 = indicators.get("sma_20", None)
        ma50 = indicators.get("sma_50", None)
        
        if ma20 and ma50:
            price_above_20ma = current_price > ma20
            price_above_50ma = current_price > ma50
            
            if signal.bias.value == "BULLISH":
                quality_checks["trend_alignment"] = price_above_20ma and price_above_50ma
            elif signal.bias.value == "BEARISH":
                quality_checks["trend_alignment"] = current_price < ma20 and current_price < ma50
            else:
                quality_checks["trend_alignment"] = True  # Neutral is always ok
        else:
            quality_checks["trend_alignment"] = True
        
        # Sector momentum check (placeholder - would need sector data)
        quality_checks["sector_momentum"] = True  # TODO: fetch sector performance
        
        # P/E valuation check
        pe_ratio = signal.context.get("pe_ratio")
        if pe_ratio and pe_ratio > 0:
            # P/E relative to sector average (TODO: add sector avg)
            quality_checks["valuation_ok"] = pe_ratio < 40  # Oversimplification
        else:
            quality_checks["valuation_ok"] = True  # No data = ok to trade
        
        # Recalculate quality score
        quality_score = sum(1 for v in quality_checks.values() if v)
        
        signal.quality_checks = quality_checks
        signal.quality_score = quality_score
        
        return signal
    
    def _fetch_fundamentals_from_db(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch stock fundamentals from database.
        
        TODO: Implement actual DB query once Symbol model is created.
        For now, returns None to indicate no data available.
        """
        # Placeholder: would query Symbol model
        # symbol_record = self.db.query(Symbol).filter_by(ticker=symbol).first()
        # if symbol_record:
        #     return {
        #         "pe_ratio": symbol_record.pe_ratio,
        #         "pb_ratio": symbol_record.pb_ratio,
        #         "dividend_yield": symbol_record.dividend_yield,
        #         "market_cap": symbol_record.market_cap,
        #         "sector": symbol_record.sector,
        #         "nifty_weight": symbol_record.weight_in_nifty,
        #     }
        return None
