"""
drawdown_tracker.py
-------------------
Phase 2 Safety Feature — Drawdown Monitoring.

Tracks peak capital vs current capital and enforces:
  - At 5% drawdown  → reduce new position sizes by 50%
  - At 10% drawdown → pause all new trades entirely

These rules prevent the classic "trying to win it all back" spiral
that destroys trading accounts.

Usage:
    from app.core.risk.drawdown_tracker import DrawdownTracker

    tracker = DrawdownTracker(db, current_capital=500000)
    
    # Check before trading
    status = tracker.get_status()
    if status["trading_paused"]:
        raise HTTPException(403, status["message"])

    # Get adjusted lot size before execution
    adjusted_lots = tracker.get_adjusted_lots(requested_lots=2)
"""

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import DailyCapital

logger = logging.getLogger(__name__)


# ── Config ────────────────────────────────────────────────────────────────
REDUCE_AT_DRAWDOWN_PCT: float = 5.0    # Reduce position size at this drawdown %
PAUSE_AT_DRAWDOWN_PCT: float = 15.0    # Halt all new trades at this drawdown %
POSITION_SIZE_REDUCTION: float = 0.5   # Scale factor when in drawdown zone (50%)


@dataclass
class DrawdownStatus:
    current_capital: float
    peak_capital: float
    drawdown_pct: float
    trading_paused: bool
    position_size_scale: float   # 1.0 = normal, 0.5 = half size
    message: str
    zone: str  # "NORMAL", "CAUTION", "HALTED"


class DrawdownTracker:
    """
    Tracks peak capital from the daily_capital table and enforces
    drawdown-based position size reductions and trading halts.
    """

    def __init__(self, db: Session, current_capital: float):
        self.db = db
        self.current_capital = current_capital

    def get_peak_capital(self) -> float:
        """
        Return highest closing_capital ever recorded in daily_capital table.
        Falls back to current_capital if no history exists yet.
        """
        peak = (
            self.db.query(func.max(DailyCapital.closing_capital))
            .filter(DailyCapital.closing_capital.isnot(None))
            .scalar()
        )
        if peak is None or peak <= 0:
            return self.current_capital
        # Peak should never be less than current (e.g. first day)
        return max(float(peak), self.current_capital)

    def get_drawdown_pct(self) -> float:
        """
        Drawdown % = (peak - current) / peak * 100.
        Returns 0.0 if at or above peak (no drawdown).
        """
        peak = self.get_peak_capital()
        if peak <= 0:
            return 0.0
        dd = (peak - self.current_capital) / peak * 100
        return max(0.0, round(dd, 2))

    def get_status(self) -> DrawdownStatus:
        """
        Full drawdown status — use this to gate trade execution and
        display the drawdown widget on the dashboard.
        """
        peak = self.get_peak_capital()
        dd_pct = self.get_drawdown_pct()

        if dd_pct >= PAUSE_AT_DRAWDOWN_PCT:
            return DrawdownStatus(
                current_capital=self.current_capital,
                peak_capital=peak,
                drawdown_pct=dd_pct,
                trading_paused=True,
                position_size_scale=0.0,
                zone="HALTED",
                message=(
                    f"⛔ Trading HALTED — drawdown {dd_pct:.1f}% exceeds "
                    f"{PAUSE_AT_DRAWDOWN_PCT:.0f}% limit. "
                    "Review strategy performance before resuming."
                ),
            )

        if dd_pct >= REDUCE_AT_DRAWDOWN_PCT:
            return DrawdownStatus(
                current_capital=self.current_capital,
                peak_capital=peak,
                drawdown_pct=dd_pct,
                trading_paused=False,
                position_size_scale=POSITION_SIZE_REDUCTION,
                zone="CAUTION",
                message=(
                    f"⚠️ Drawdown {dd_pct:.1f}% — position sizes reduced to "
                    f"{int(POSITION_SIZE_REDUCTION * 100)}% until capital recovers."
                ),
            )

        return DrawdownStatus(
            current_capital=self.current_capital,
            peak_capital=peak,
            drawdown_pct=dd_pct,
            trading_paused=False,
            position_size_scale=1.0,
            zone="NORMAL",
            message=f"✅ Drawdown {dd_pct:.1f}% — within normal range.",
        )

    def get_adjusted_lots(self, requested_lots: int) -> int:
        """
        Scale lot count based on current drawdown zone.
        Always returns at least 1 lot if trading is allowed.

        Args:
            requested_lots: What the strategy wants to trade

        Returns:
            Adjusted lot count (may be reduced or 0 if halted)
        """
        status = self.get_status()

        if status.trading_paused:
            logger.warning(
                f"DrawdownTracker: trading paused at {status.drawdown_pct:.1f}% drawdown. "
                "Returning 0 lots."
            )
            return 0

        adjusted = max(1, int(requested_lots * status.position_size_scale))

        if adjusted < requested_lots:
            logger.info(
                f"DrawdownTracker: reduced lots {requested_lots} → {adjusted} "
                f"(drawdown {status.drawdown_pct:.1f}%, scale {status.position_size_scale})"
            )

        return adjusted

    def to_dict(self) -> dict:
        """Serialise status for API responses and dashboard widget."""
        s = self.get_status()
        return {
            "current_capital": round(s.current_capital, 2),
            "peak_capital": round(s.peak_capital, 2),
            "drawdown_pct": s.drawdown_pct,
            "drawdown_amount": round(s.peak_capital - s.current_capital, 2),
            "trading_paused": s.trading_paused,
            "position_size_scale": s.position_size_scale,
            "zone": s.zone,
            "message": s.message,
            "thresholds": {
                "reduce_at_pct": REDUCE_AT_DRAWDOWN_PCT,
                "pause_at_pct": PAUSE_AT_DRAWDOWN_PCT,
            },
        }
