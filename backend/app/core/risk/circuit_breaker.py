"""
circuit_breaker.py
------------------
Phase 2 Safety Feature — Circuit Breaker System.

Enforces hard limits during a live trading session:
  1. Daily loss limit        — halt if today's PnL loss % >= threshold
  2. Max positions per underlying — e.g. max 3 NIFTY positions open
  3. Max total open positions     — e.g. max 10 across all underlyings
  4. Concentration limit          — single underlying <= 50% of open positions
  5. Cooling period               — mandatory rest after a forced halt

All checks return a CircuitBreakerResult so the caller knows *why* trading
was blocked, and the UI can display a clear reason.

Usage (in execute.py, execution_v2.py, etc.):
    from app.core.risk.circuit_breaker import CircuitBreaker, CircuitBreakerTripped

    cb = CircuitBreaker(db, capital)
    cb.check_all(underlying="NIFTY")   # raises CircuitBreakerTripped if blocked
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func, cast, Date
from sqlalchemy.orm import Session

from app.core.utils.time import now_ist
from app.db.models_intent import ExecutionIntent
from app.db.models import DailyCapital
from app.core.risk.risk_limits_config import get_risk_limits

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Config constants  (override via env or DB later)
# ─────────────────────────────────────────────
MAX_POSITIONS_PER_UNDERLYING: int = 3
MAX_TOTAL_OPEN_POSITIONS: int = 10
MAX_CONCENTRATION_PCT: float = 50.0   # single underlying can't be > 50% of all open positions
COOLING_PERIOD_MINUTES: int = 30       # minutes to pause after a forced circuit-break


# ─────────────────────────────────────────────
# Result + Exception types
# ─────────────────────────────────────────────
@dataclass
class CircuitBreakerResult:
    allowed: bool
    reason: str = ""
    detail: str = ""

    def __bool__(self):
        return self.allowed


class CircuitBreakerTripped(Exception):
    """Raised by CircuitBreaker.check_all() when trading must be halted."""
    def __init__(self, reason: str, detail: str = ""):
        self.reason = reason
        self.detail = detail
        super().__init__(f"CIRCUIT BREAKER: {reason} — {detail}")


# ─────────────────────────────────────────────
# Main class
# ─────────────────────────────────────────────
class CircuitBreaker:
    """
    Stateless per-request circuit breaker.
    Instantiate with a DB session and current capital, then call check_all().
    """

    def __init__(self, db: Session, capital: float):
        self.db = db
        self.capital = capital
        self.risk_config = get_risk_limits(db=db)

    # ── PUBLIC ENTRY POINT ──────────────────────────────────────────────────

    def check_all(self, underlying: Optional[str] = None) -> None:
        """
        Run all circuit-breaker checks in priority order.
        Raises CircuitBreakerTripped on the first failure.
        Call this before every trade execution.
        """
        checks = [
            self.check_daily_loss,
            self.check_total_positions,
            self.check_cooling_period,
        ]
        if underlying:
            checks.insert(1, lambda: self.check_positions_per_underlying(underlying))
            checks.insert(2, lambda: self.check_concentration(underlying))

        for check in checks:
            result = check()
            if not result.allowed:
                logger.warning(
                    f"🚫 Circuit breaker tripped: {result.reason} — {result.detail}"
                )
                raise CircuitBreakerTripped(result.reason, result.detail)

        logger.debug("✅ All circuit-breaker checks passed")

    # ── INDIVIDUAL CHECKS ────────────────────────────────────────────────────

    def check_daily_loss(self) -> CircuitBreakerResult:
        """Block if today's realised + unrealised loss >= daily loss limit."""
        today = date.today()

        today_pnl = (
            self.db.query(func.sum(ExecutionIntent.pnl))
            .filter(
                ExecutionIntent.pnl.isnot(None),
                ExecutionIntent.status.in_(["EXECUTED", "CLOSED"]),
                cast(ExecutionIntent.created_at, Date) == today,
            )
            .scalar()
            or 0.0
        )

        if today_pnl >= 0:
            return CircuitBreakerResult(allowed=True)

        loss_pct = abs(today_pnl) / self.capital * 100
        limit_pct = self.risk_config.max_portfolio_loss_pct

        if loss_pct >= limit_pct:
            return CircuitBreakerResult(
                allowed=False,
                reason="DAILY_LOSS_LIMIT",
                detail=(
                    f"Today's loss ₹{abs(today_pnl):,.0f} "
                    f"({loss_pct:.1f}%) >= limit {limit_pct:.1f}%. "
                    "No new trades allowed today."
                ),
            )
        return CircuitBreakerResult(allowed=True)

    def check_positions_per_underlying(self, underlying: str) -> CircuitBreakerResult:
        """Block if underlying already has MAX_POSITIONS_PER_UNDERLYING open positions."""
        count = (
            self.db.query(func.count(ExecutionIntent.id))
            .filter(
                ExecutionIntent.status == "EXECUTED",
                ExecutionIntent.underlying == underlying.upper(),
            )
            .scalar()
            or 0
        )

        if count >= MAX_POSITIONS_PER_UNDERLYING:
            return CircuitBreakerResult(
                allowed=False,
                reason="MAX_POSITIONS_PER_UNDERLYING",
                detail=(
                    f"{underlying} already has {count} open position(s). "
                    f"Limit is {MAX_POSITIONS_PER_UNDERLYING}. "
                    "Close an existing position before opening a new one."
                ),
            )
        return CircuitBreakerResult(allowed=True)

    def check_total_positions(self) -> CircuitBreakerResult:
        """Block if total open positions across all underlyings >= MAX_TOTAL_OPEN_POSITIONS."""
        total = (
            self.db.query(func.count(ExecutionIntent.id))
            .filter(ExecutionIntent.status == "EXECUTED")
            .scalar()
            or 0
        )

        if total >= MAX_TOTAL_OPEN_POSITIONS:
            return CircuitBreakerResult(
                allowed=False,
                reason="MAX_TOTAL_POSITIONS",
                detail=(
                    f"Total open positions: {total}. "
                    f"Limit is {MAX_TOTAL_OPEN_POSITIONS}. "
                    "Close some positions before opening new ones."
                ),
            )
        return CircuitBreakerResult(allowed=True)

    def check_concentration(self, underlying: str) -> CircuitBreakerResult:
        """Block if a single underlying would exceed MAX_CONCENTRATION_PCT of total positions."""
        total = (
            self.db.query(func.count(ExecutionIntent.id))
            .filter(ExecutionIntent.status == "EXECUTED")
            .scalar()
            or 0
        )

        if total == 0:
            return CircuitBreakerResult(allowed=True)

        underlying_count = (
            self.db.query(func.count(ExecutionIntent.id))
            .filter(
                ExecutionIntent.status == "EXECUTED",
                ExecutionIntent.underlying == underlying.upper(),
            )
            .scalar()
            or 0
        )

        # Would adding 1 breach the limit?
        new_pct = (underlying_count + 1) / (total + 1) * 100
        if new_pct > MAX_CONCENTRATION_PCT:
            return CircuitBreakerResult(
                allowed=False,
                reason="CONCENTRATION_LIMIT",
                detail=(
                    f"Adding a {underlying} position would make it "
                    f"{new_pct:.0f}% of your portfolio. "
                    f"Limit is {MAX_CONCENTRATION_PCT:.0f}%. "
                    "Diversify across other underlyings."
                ),
            )
        return CircuitBreakerResult(allowed=True)

    def check_cooling_period(self) -> CircuitBreakerResult:
        """
        Block if a forced circuit-break happened recently and cooling period hasn't elapsed.
        A forced break is detected by finding a CLOSED intent with exit_reason = 'CIRCUIT_BREAK'
        within the last COOLING_PERIOD_MINUTES.
        """
        cutoff = now_ist() - timedelta(minutes=COOLING_PERIOD_MINUTES)

        recent_break = (
            self.db.query(ExecutionIntent)
            .filter(
                ExecutionIntent.exit_reason == "CIRCUIT_BREAK",
                ExecutionIntent.closed_at.isnot(None),
                ExecutionIntent.closed_at >= cutoff,
            )
            .first()
        )

        if recent_break:
            elapsed = now_ist() - recent_break.closed_at
            remaining_mins = COOLING_PERIOD_MINUTES - int(elapsed.total_seconds() / 60)
            return CircuitBreakerResult(
                allowed=False,
                reason="COOLING_PERIOD",
                detail=(
                    f"A circuit break was triggered {int(elapsed.total_seconds() / 60)} min ago. "
                    f"Cooling period: {remaining_mins} min remaining. "
                    "This prevents revenge trading after a forced halt."
                ),
            )

        return CircuitBreakerResult(allowed=True)

    # ── STATUS SUMMARY (for dashboard / health endpoint) ──────────────────

    def get_status(self, underlying: Optional[str] = None) -> dict:
        """
        Return a full status dict for the dashboard.
        Does NOT raise — returns allowed=True/False per check.
        """
        today = date.today()

        today_pnl = (
            self.db.query(func.sum(ExecutionIntent.pnl))
            .filter(
                ExecutionIntent.pnl.isnot(None),
                ExecutionIntent.status.in_(["EXECUTED", "CLOSED"]),
                cast(ExecutionIntent.created_at, Date) == today,
            )
            .scalar()
            or 0.0
        )

        total_open = (
            self.db.query(func.count(ExecutionIntent.id))
            .filter(ExecutionIntent.status == "EXECUTED")
            .scalar()
            or 0
        )

        underlying_open = 0
        if underlying:
            underlying_open = (
                self.db.query(func.count(ExecutionIntent.id))
                .filter(
                    ExecutionIntent.status == "EXECUTED",
                    ExecutionIntent.underlying == underlying.upper(),
                )
                .scalar()
                or 0
            )

        loss_pct = abs(today_pnl) / self.capital * 100 if today_pnl < 0 else 0.0

        return {
            "trading_allowed": loss_pct < self.risk_config.max_portfolio_loss_pct
                               and total_open < MAX_TOTAL_OPEN_POSITIONS,
            "daily_pnl": round(today_pnl, 2),
            "daily_loss_pct": round(loss_pct, 2),
            "daily_loss_limit_pct": self.risk_config.max_portfolio_loss_pct,
            "total_open_positions": total_open,
            "max_total_positions": MAX_TOTAL_OPEN_POSITIONS,
            "underlying_open_positions": underlying_open,
            "max_per_underlying": MAX_POSITIONS_PER_UNDERLYING,
            "cooling_period_minutes": COOLING_PERIOD_MINUTES,
        }
