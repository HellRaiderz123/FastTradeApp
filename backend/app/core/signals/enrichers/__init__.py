"""
Enrichers for asset-specific signal enhancement.

Each enricher adds domain-specific fields to the base Signal:
- StockEnricher: Fundamentals, sector, market cap, P/E, dividend yield
- OptionEnricher: Greeks, IV skew, open interest, time decay
- FutureEnricher: Contract specs, basis, roll dates, open interest
- IndexEnricher: Constituent heatmap, breadth, market cap concentration
"""

from .stock_enricher import StockEnricher
from .option_enricher import OptionEnricher
from .future_enricher import FutureEnricher
from .index_enricher import IndexEnricher

__all__ = [
    "StockEnricher",
    "OptionEnricher",
    "FutureEnricher",
    "IndexEnricher",
]
