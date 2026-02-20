"""
Spread Detection Data Models
Defines structures for detected spreads and position groupings.
"""

from typing import List, Dict, Literal, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import date


# Spread type definitions
SpreadType = Literal[
    "BULL_CALL_SPREAD",
    "BULL_PUT_SPREAD",
    "BEAR_CALL_SPREAD",
    "BEAR_PUT_SPREAD",
    "IRON_CONDOR",
    "BUTTERFLY_CALL",
    "BUTTERFLY_PUT",
    "LONG_STRADDLE",
    "SHORT_STRADDLE",
    "LONG_STRANGLE",
    "SHORT_STRANGLE",
    "CALENDAR_SPREAD",
    "RATIO_CALL_BACKSPREAD",
    "RATIO_PUT_BACKSPREAD",
    "CALL_RATIO_SPREAD",
    "PUT_RATIO_SPREAD",
    "NAKED_CALL",
    "NAKED_PUT",
    "INCOMPLETE_SPREAD",
]

WarningLevel = Literal["INFO", "WARNING", "CRITICAL"]


@dataclass
class PositionLeg:
    """Single position leg (part of a spread or naked)"""
    intent_id: str
    strategy: str
    side: Literal["BUY", "SELL"]
    option_type: Literal["CE", "PE"]
    strike: int
    quantity: int
    expiry: Optional[str] = None
    underlying: Optional[str] = None
    entry_credit: Optional[float] = None
    entry_price: Optional[float] = None  # Per-unit entry price for this leg
    pnl: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    current_ltp: Optional[float] = None


@dataclass
class SpreadWarning:
    """Warning about incomplete spreads or naked positions"""
    level: WarningLevel
    message: str
    affected_intent_ids: List[str]
    missing_legs: Optional[List[Dict]] = None


@dataclass
class DetectedSpread:
    """A detected spread pattern"""
    spread_type: SpreadType
    underlying: str
    expiry: Optional[str]
    legs: List[PositionLeg]
    confidence: float  # 0-1, how confident are we this is a real spread
    warnings: List[SpreadWarning]
    max_profit: Optional[float] = None
    max_loss: Optional[float] = None
    breakeven_points: Optional[List[float]] = None
    
    def to_dict(self):
        return {
            "spread_type": self.spread_type,
            "underlying": self.underlying,
            "expiry": self.expiry,
            "legs": [asdict(leg) for leg in self.legs],
            "confidence": self.confidence,
            "warnings": [asdict(w) for w in self.warnings],
            "max_profit": self.max_profit,
            "max_loss": self.max_loss,
            "breakeven_points": self.breakeven_points,
        }


@dataclass
class GroupedPositions:
    """Grouped positions: spreads + unmatched positions"""
    spreads: List[DetectedSpread]
    naked_positions: List[PositionLeg]
    incomplete_spreads: List[Tuple[PositionLeg, SpreadWarning]]
    total_warnings: List[SpreadWarning]
    
    def has_critical_warnings(self) -> bool:
        return any(w.level == "CRITICAL" for w in self.total_warnings)
    
    def to_dict(self):
        return {
            "spreads": [s.to_dict() for s in self.spreads],
            "naked_positions": [asdict(leg) for leg in self.naked_positions],
            "incomplete_spreads": [
                {
                    "leg": asdict(leg),
                    "warning": asdict(warning)
                }
                for leg, warning in self.incomplete_spreads
            ],
            "total_warnings": [asdict(w) for w in self.total_warnings],
            "has_critical_warnings": self.has_critical_warnings(),
        }
