"""
risk.py
-------
Hard risk gates for option spreads.
If risk.py blocks → trade is NOT allowed.
"""

from typing import Tuple, Dict, Optional
from app.core.risk.risk_limits_config import RiskLimits, DEFAULT_RISK_LIMITS

def pct_from_atm(strike: int, spot: float) -> float:
    """
    Percentage distance of strike from spot.
    """
    return abs(strike - spot) / spot * 100.0


def get_risk_limits(
    iv_regime: str,
    config: Optional[RiskLimits] = None
) -> Dict[str, float]:
    """
    Get risk limits for IV regime from configuration.
    
    Args:
        iv_regime: One of 'LOW', 'NORMAL', 'HIGH'
        config: RiskLimits config object (uses default if None)
        
    Returns:
        Dict with 'min_atm_dist_pct' and 'max_risk_pct_capital'
    """
    if config is None:
        config = DEFAULT_RISK_LIMITS
    
    return config.get_iv_regime_limits(iv_regime)


def check_spread_risk(
    *,
    short_strike: int,
    long_strike: int,
    spot: float,
    capital: float,
    lot_size: int,
    lots: int,
    iv_regime: str,
    risk_config: Optional[RiskLimits] = None,
) -> Tuple[bool, str, Dict[str, float]]:

    metrics: Dict[str, float] = {}

    limits = get_risk_limits(iv_regime, risk_config)

    # ============================
    # THEORETICAL RISK (ALWAYS)
    # ============================
    width = abs(short_strike - long_strike)
    max_loss = width * lot_size * lots
    metrics["max_loss"] = max_loss

    if capital > 0:
        risk_pct = (max_loss / capital) * 100.0
    else:
        risk_pct = float("inf")

    metrics["risk_pct_capital"] = risk_pct

    # ============================
    # STRUCTURE CHECK
    # ============================
    dist_pct = pct_from_atm(short_strike, spot)
    metrics["strike_dist_pct"] = dist_pct

    if dist_pct < limits["min_atm_dist_pct"]:
        return (
            False,
            f"Strike too close to ATM ({dist_pct:.2f}% < {limits['min_atm_dist_pct']}%)",
            metrics,
        )

    # ============================
    # CAPITAL RISK CHECK
    # ============================
    if capital <= 0:
        return (
            False,
            "Capital not available",
            metrics,
        )

    if risk_pct > limits["max_risk_pct_capital"]:
        return (
            False,
            f"Risk {risk_pct:.2f}% exceeds limit {limits['max_risk_pct_capital']}%",
            metrics,
        )

    # ============================
    # PASSED ALL CHECKS
    # ============================
    return True, "Risk within limits", metrics
