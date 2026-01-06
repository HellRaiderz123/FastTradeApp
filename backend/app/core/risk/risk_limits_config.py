"""
risk_limits_config.py
---------------------
Configurable risk limits system.
Allows different traders/strategies to have different risk parameters.
"""

from typing import Dict, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class RiskLimits:
    """Risk limits configuration for a trade session."""
    
    # Portfolio-level limits
    max_portfolio_loss_pct: float = 3.0  # Max % of capital that can be lost
    max_trades_per_day: int = 3          # Max number of trades per day
    
    # IV-regime specific limits
    iv_regime_limits: Dict[str, Dict[str, float]] = field(
        default_factory=lambda: {
            "LOW": {
                "min_atm_dist_pct": 0.5,
                "max_risk_pct_capital": 4.0,
            },
            "NORMAL": {
                "min_atm_dist_pct": 0.6,
                "max_risk_pct_capital": 2.0,
            },
            "HIGH": {
                "min_atm_dist_pct": 0.8,
                "max_risk_pct_capital": 5.0,
            },
        }
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def get_iv_regime_limits(self, iv_regime: str) -> Dict[str, float]:
        """Get limits for specific IV regime."""
        return self.iv_regime_limits.get(
            iv_regime,
            self.iv_regime_limits.get("NORMAL", {})
        )


@dataclass
class RiskProfile:
    """Pre-defined risk profiles for quick configuration."""
    
    CONSERVATIVE = RiskLimits(
        max_portfolio_loss_pct=1.0,
        max_trades_per_day=1,
        iv_regime_limits={
            "LOW": {"min_atm_dist_pct": 0.5, "max_risk_pct_capital": 2.0},
            "NORMAL": {"min_atm_dist_pct": 0.6, "max_risk_pct_capital": 1.5},
            "HIGH": {"min_atm_dist_pct": 0.8, "max_risk_pct_capital": 5.0},
        }
    )
    
    BALANCED = RiskLimits(
        max_portfolio_loss_pct=3.0,
        max_trades_per_day=3,
        iv_regime_limits={
            "LOW": {"min_atm_dist_pct": 0.5, "max_risk_pct_capital": 4.0},
            "NORMAL": {"min_atm_dist_pct": 0.6, "max_risk_pct_capital": 2.0},
            "HIGH": {"min_atm_dist_pct": 0.8, "max_risk_pct_capital": 5.0},
        }
    )
    
    AGGRESSIVE = RiskLimits(
        max_portfolio_loss_pct=5.0,
        max_trades_per_day=5,
        iv_regime_limits={
            "LOW": {"min_atm_dist_pct": 0.3, "max_risk_pct_capital": 6.0},
            "NORMAL": {"min_atm_dist_pct": 0.4, "max_risk_pct_capital": 3.5},
            "HIGH": {"min_atm_dist_pct": 0.6, "max_risk_pct_capital": 2.0},
        }
    )


def get_risk_limits(
    profile: Optional[str] = None,
    custom_limits: Optional[RiskLimits] = None,
) -> RiskLimits:
    """
    Get risk limits by profile name or custom configuration.
    
    Args:
        profile: One of 'conservative', 'balanced', 'aggressive'
        custom_limits: Custom RiskLimits object to use
        
    Returns:
        RiskLimits object with configured limits
    """
    if custom_limits:
        return custom_limits
    
    if not profile:
        return RiskProfile.BALANCED  # Default
    
    profile_lower = profile.lower()
    
    if profile_lower == "conservative":
        return RiskProfile.CONSERVATIVE
    elif profile_lower == "balanced":
        return RiskProfile.BALANCED
    elif profile_lower == "aggressive":
        return RiskProfile.AGGRESSIVE
    else:
        return RiskProfile.BALANCED


# Default (backward compatible)
DEFAULT_RISK_LIMITS = RiskProfile.BALANCED
