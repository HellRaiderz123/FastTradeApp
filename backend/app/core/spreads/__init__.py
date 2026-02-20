"""
Spread Detection Package
Main entry point for spread detection and grouping functionality.
"""

from .detector import SpreadDetector, detect_spreads
from .models import (
    PositionLeg,
    DetectedSpread,
    GroupedPositions,
    SpreadWarning,
    SpreadType,
)

__all__ = [
    "SpreadDetector",
    "detect_spreads",
    "PositionLeg",
    "DetectedSpread",
    "GroupedPositions",
    "SpreadWarning",
    "SpreadType",
]
