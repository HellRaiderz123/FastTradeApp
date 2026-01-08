"""
Configurable risk limits system backed by the database.

Falls back to environment variables and baked-in defaults if the DB table
is missing or unreachable so trades can still progress in degraded mode.
"""

import logging
import os
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.db.risk_repo import get_or_create_risk_limits
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


DEFAULT_IV_REGIME_LIMITS = {
    "LOW": {"min_atm_dist_pct": 0.5, "max_risk_pct_capital": 4.0},
    "NORMAL": {"min_atm_dist_pct": 0.6, "max_risk_pct_capital": 2.0},
    "HIGH": {"min_atm_dist_pct": 0.8, "max_risk_pct_capital": 5.0},
}


@dataclass
class RiskLimits:
    """Risk limits configuration for a trade session."""

    # Portfolio-level limits
    max_portfolio_loss_pct: float = 2.0  # Max % of capital that can be lost per trade
    max_trades_per_day: int = 3  # Max number of trades per day

    # IV-regime specific limits
    iv_regime_limits: Dict[str, Dict[str, float]] = field(
        default_factory=lambda: deepcopy(DEFAULT_IV_REGIME_LIMITS)
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def get_iv_regime_limits(self, iv_regime: str) -> Dict[str, float]:
        """Get limits for specific IV regime."""
        return self.iv_regime_limits.get(
            iv_regime,
            self.iv_regime_limits.get("NORMAL", {}),
        )


def _clone_limits(limits: RiskLimits) -> RiskLimits:
    return RiskLimits(
        max_portfolio_loss_pct=limits.max_portfolio_loss_pct,
        max_trades_per_day=limits.max_trades_per_day,
        iv_regime_limits=deepcopy(limits.iv_regime_limits),
    )


class RiskProfile:
    """Pre-defined risk profiles for quick configuration (env fallback)."""

    CONSERVATIVE = RiskLimits(
        max_portfolio_loss_pct=1.0,
        max_trades_per_day=1,
        iv_regime_limits={
            "LOW": {"min_atm_dist_pct": 0.5, "max_risk_pct_capital": 2.0},
            "NORMAL": {"min_atm_dist_pct": 0.6, "max_risk_pct_capital": 1.5},
            "HIGH": {"min_atm_dist_pct": 0.8, "max_risk_pct_capital": 5.0},
        },
    )

    BALANCED = RiskLimits(
        max_portfolio_loss_pct=3.0,
        max_trades_per_day=3,
        iv_regime_limits=deepcopy(DEFAULT_IV_REGIME_LIMITS),
    )

    AGGRESSIVE = RiskLimits(
        max_portfolio_loss_pct=5.0,
        max_trades_per_day=5,
        iv_regime_limits={
            "LOW": {"min_atm_dist_pct": 0.3, "max_risk_pct_capital": 6.0},
            "NORMAL": {"min_atm_dist_pct": 0.4, "max_risk_pct_capital": 3.5},
            "HIGH": {"min_atm_dist_pct": 0.6, "max_risk_pct_capital": 2.0},
        },
    )


def _apply_env_overrides(limits: RiskLimits) -> RiskLimits:
    """Override provided limits with dynamic environment values (fallback)."""
    max_trades = int(os.getenv("MAX_TRADES_PER_DAY", limits.max_trades_per_day))
    risk_per_trade = float(os.getenv("RISK_PER_TRADE", limits.max_portfolio_loss_pct))
    limits.max_trades_per_day = max_trades
    limits.max_portfolio_loss_pct = risk_per_trade
    return limits


def _load_from_db(db: Session | None = None) -> Optional[RiskLimits]:
    """Fetch risk limits from DB. Returns None if table is missing/unavailable."""
    external_session = db is not None
    session = db or SessionLocal()

    try:
        record = get_or_create_risk_limits(session)
        return RiskLimits(
            max_portfolio_loss_pct=record.max_portfolio_loss_pct,
            max_trades_per_day=record.max_trades_per_day,
            iv_regime_limits=deepcopy(record.iv_regime_limits or DEFAULT_IV_REGIME_LIMITS),
        )
    except Exception:
        logger.warning("Risk limits DB fetch failed; falling back to env/defaults", exc_info=True)
        return None
    finally:
        if not external_session:
            session.close()


def _profile_limits(profile: Optional[str]) -> RiskLimits:
    if not profile:
        return _clone_limits(RiskProfile.BALANCED)

    profile_lower = profile.lower()
    if profile_lower == "conservative":
        return _clone_limits(RiskProfile.CONSERVATIVE)
    if profile_lower == "aggressive":
        return _clone_limits(RiskProfile.AGGRESSIVE)
    return _clone_limits(RiskProfile.BALANCED)


def get_risk_limits(
    profile: Optional[str] = None,
    custom_limits: Optional[RiskLimits] = None,
    db: Session | None = None,
) -> RiskLimits:
    """Return risk limits from DB first, else env/profile defaults."""
    if custom_limits:
        return custom_limits

    db_limits = _load_from_db(db)
    if db_limits:
        return db_limits

    # Fallback path: profile + env overrides
    limits = _profile_limits(profile)
    return _apply_env_overrides(limits)


# Default (backward compatible)
DEFAULT_RISK_LIMITS = _clone_limits(RiskProfile.BALANCED)
