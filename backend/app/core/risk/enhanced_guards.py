"""
Enhanced Risk Guards — Portfolio Greeks, VIX Kill-Switch, Time-of-Day Guard.

Phase 5: Risk Guards Upgrade
"""

import logging
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class RiskCheckResult:
    """Result of a risk check."""
    passed: bool
    reason: str = ""
    action: str = "ALLOW"  # ALLOW, BLOCK, REDUCE_SIZE
    size_multiplier: float = 1.0


class PortfolioGreeksGuard:
    """
    Block trades if portfolio net delta exceeds limits or sector concentration is too high.
    """

    def __init__(
        self,
        max_net_delta: float = 500.0,
        max_sector_positions: int = 3,
    ):
        self.max_net_delta = max_net_delta
        self.max_sector_positions = max_sector_positions
        
        # NSE sector mapping (simplified)
        self.sector_map: Dict[str, str] = {
            "RELIANCE": "ENERGY", "ONGC": "ENERGY", "BPCL": "ENERGY", "IOC": "ENERGY",
            "TCS": "IT", "INFY": "IT", "WIPRO": "IT", "HCLTECH": "IT", "TECHM": "IT",
            "HDFCBANK": "BANKING", "ICICIBANK": "BANKING", "SBIN": "BANKING", "AXISBANK": "BANKING",
            "SUNPHARMA": "PHARMA", "CIPLA": "PHARMA", "DRREDDY": "PHARMA", "DIVISLAB": "PHARMA",
            "MARUTI": "AUTO", "TATAMOTORS": "AUTO", "M&M": "AUTO", "BAJAJ-AUTO": "AUTO",
            "TATASTEEL": "METAL", "JSWSTEEL": "METAL", "HINDALCO": "METAL", "VEDL": "METAL",
        }

    def check(
        self,
        db: Session,
        new_symbol: str,
        new_delta: float,
    ) -> RiskCheckResult:
        """
        Check if new trade violates portfolio Greeks or concentration limits.
        
        Args:
            db: Database session
            new_symbol: Symbol of new trade
            new_delta: Delta of new position
        """
        try:
            from app.db.models_intent import ExecutionIntent
            
            # Get open positions
            open_positions = (
                db.query(ExecutionIntent)
                .filter(
                    ExecutionIntent.status == "EXECUTED",
                    ExecutionIntent.closed_at.is_(None),
                )
                .all()
            )
            
            # Calculate current portfolio delta
            current_delta = sum(
                float(getattr(pos, "delta", 0) or 0)
                for pos in open_positions
            )
            
            # Check delta limit
            projected_delta = current_delta + new_delta
            if abs(projected_delta) > self.max_net_delta:
                return RiskCheckResult(
                    passed=False,
                    reason=f"Portfolio delta would exceed limit: {projected_delta:.0f} > {self.max_net_delta}",
                    action="BLOCK",
                )
            
            # Check sector concentration
            new_sector = self.sector_map.get(new_symbol.upper(), "OTHER")
            sector_count: Dict[str, int] = {}
            
            for pos in open_positions:
                underlying = str(getattr(pos, "underlying", "") or "").upper()
                sector = self.sector_map.get(underlying, "OTHER")
                sector_count[sector] = sector_count.get(sector, 0) + 1
            
            if sector_count.get(new_sector, 0) >= self.max_sector_positions:
                return RiskCheckResult(
                    passed=False,
                    reason=f"Too many positions in {new_sector} sector: {sector_count[new_sector]} >= {self.max_sector_positions}",
                    action="BLOCK",
                )
            
            return RiskCheckResult(passed=True)
            
        except Exception as e:
            logger.warning("PortfolioGreeksGuard.check failed: %s", e)
            return RiskCheckResult(passed=True)  # Fail open


class VIXKillSwitch:
    """
    Tighten position sizes when India VIX spikes.
    """

    def __init__(
        self,
        vix_spike_threshold_pct: float = 15.0,
        size_reduction_factor: float = 0.5,
        vix_absolute_threshold: float = 25.0,
    ):
        self.vix_spike_threshold_pct = vix_spike_threshold_pct
        self.size_reduction_factor = size_reduction_factor
        self.vix_absolute_threshold = vix_absolute_threshold
        self._last_vix: Optional[float] = None
        self._vix_open: Optional[float] = None

    def check(self, current_vix: float) -> RiskCheckResult:
        """
        Check if VIX spike requires position size reduction.
        
        Args:
            current_vix: Current India VIX value
        """
        # Store opening VIX (first check of the day)
        if self._vix_open is None:
            self._vix_open = current_vix
        
        # Check absolute threshold
        if current_vix > self.vix_absolute_threshold:
            return RiskCheckResult(
                passed=True,
                reason=f"VIX at {current_vix:.1f} > {self.vix_absolute_threshold}. Reducing size by 50%.",
                action="REDUCE_SIZE",
                size_multiplier=self.size_reduction_factor,
            )
        
        # Check intraday spike
        if self._vix_open and self._vix_open > 0:
            spike_pct = ((current_vix - self._vix_open) / self._vix_open) * 100
            if spike_pct > self.vix_spike_threshold_pct:
                return RiskCheckResult(
                    passed=True,
                    reason=f"VIX spiked {spike_pct:.1f}% intraday. Reducing size by 50%.",
                    action="REDUCE_SIZE",
                    size_multiplier=self.size_reduction_factor,
                )
        
        self._last_vix = current_vix
        return RiskCheckResult(passed=True)

    def reset_daily(self) -> None:
        """Reset for new trading day."""
        self._vix_open = None
        self._last_vix = None


class TimeOfDayGuard:
    """
    Block new entries after cutoff time and warn before square-off.
    """

    def __init__(
        self,
        entry_cutoff: time = time(14, 45),
        square_off_warning: time = time(15, 15),
        square_off_time: time = time(15, 20),
    ):
        self.entry_cutoff = entry_cutoff
        self.square_off_warning = square_off_warning
        self.square_off_time = square_off_time

    def check_entry(self) -> RiskCheckResult:
        """Check if new intraday entries are allowed."""
        now = datetime.now().time()
        
        if now >= self.entry_cutoff:
            return RiskCheckResult(
                passed=False,
                reason=f"New intraday entries blocked after {self.entry_cutoff.strftime('%H:%M')} IST",
                action="BLOCK",
            )
        
        return RiskCheckResult(passed=True)

    def check_square_off(self) -> RiskCheckResult:
        """Check if square-off warning/action is needed."""
        now = datetime.now().time()
        
        if now >= self.square_off_time:
            return RiskCheckResult(
                passed=False,
                reason=f"Auto square-off triggered at {self.square_off_time.strftime('%H:%M')} IST",
                action="SQUARE_OFF",
            )
        
        if now >= self.square_off_warning:
            return RiskCheckResult(
                passed=True,
                reason=f"Square-off warning: {(datetime.combine(datetime.today(), self.square_off_time) - datetime.combine(datetime.today(), now)).seconds // 60} minutes remaining",
                action="WARN",
            )
        
        return RiskCheckResult(passed=True)


class RiskGuardManager:
    """
    Unified risk guard manager that runs all checks.
    """

    def __init__(self):
        self.portfolio_guard = PortfolioGreeksGuard()
        self.vix_guard = VIXKillSwitch()
        self.time_guard = TimeOfDayGuard()

    def check_new_trade(
        self,
        db: Session,
        symbol: str,
        delta: float = 0.0,
        current_vix: Optional[float] = None,
        is_intraday: bool = True,
    ) -> Dict[str, Any]:
        """
        Run all risk checks for a new trade.
        
        Returns:
            Dict with:
                - allowed: bool
                - size_multiplier: float (1.0 = full size)
                - warnings: List[str]
                - blocks: List[str]
        """
        result = {
            "allowed": True,
            "size_multiplier": 1.0,
            "warnings": [],
            "blocks": [],
        }
        
        # Portfolio Greeks check
        portfolio_check = self.portfolio_guard.check(db, symbol, delta)
        if not portfolio_check.passed:
            result["allowed"] = False
            result["blocks"].append(portfolio_check.reason)
        
        # VIX check
        if current_vix is not None:
            vix_check = self.vix_guard.check(current_vix)
            if vix_check.action == "REDUCE_SIZE":
                result["size_multiplier"] *= vix_check.size_multiplier
                result["warnings"].append(vix_check.reason)
        
        # Time of day check (for intraday)
        if is_intraday:
            time_check = self.time_guard.check_entry()
            if not time_check.passed:
                result["allowed"] = False
                result["blocks"].append(time_check.reason)
            
            sq_check = self.time_guard.check_square_off()
            if sq_check.action == "WARN":
                result["warnings"].append(sq_check.reason)
            elif sq_check.action == "SQUARE_OFF":
                result["allowed"] = False
                result["blocks"].append(sq_check.reason)
        
        return result

    def reset_daily(self) -> None:
        """Reset daily state for all guards."""
        self.vix_guard.reset_daily()


# Singleton instance
_guard_manager: Optional[RiskGuardManager] = None


def get_risk_guard_manager() -> RiskGuardManager:
    """Get singleton RiskGuardManager."""
    global _guard_manager
    if _guard_manager is None:
        _guard_manager = RiskGuardManager()
    return _guard_manager
