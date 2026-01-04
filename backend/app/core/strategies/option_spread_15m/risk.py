"""
risk.py
-------
Hard risk gates for option spreads.
If risk.py blocks → trade is NOT allowed.
"""

from typing import Tuple, Dict

MAX_PORTFOLIO_LOSS_PCT = 3.0  # % of capital
MAX_TRADES_PER_DAY = 3

def pct_from_atm(strike: int, spot: float) -> float:
    """
    Percentage distance of strike from spot.
    """
    return abs(strike - spot) / spot * 100.0


def get_risk_limits(iv_regime: str) -> Dict[str, float]:
    """
    Risk limits exactly as in your Streamlit code.
    """
    if iv_regime == "LOW":
        return {
            "min_atm_dist_pct": 0.5,
            "max_risk_pct_capital": 4.0,
        }
    elif iv_regime == "NORMAL":
        return {
            "min_atm_dist_pct": 0.6,
            "max_risk_pct_capital": 2.0,
        }
    else:  # HIGH IV
        return {
            "min_atm_dist_pct": 0.8,
            "max_risk_pct_capital": 1.0,
        }


def check_spread_risk(
    *,
    short_strike: int,
    long_strike: int,
    spot: float,
    capital: float,
    lot_size: int,
    lots: int,
    iv_regime: str,
) -> Tuple[bool, str, Dict[str, float]]:
    """
    Final risk gate for spread.

    Returns:
        (is_safe, reason, metrics)
    """

    metrics: Dict[str, float] = {}

    limits = get_risk_limits(iv_regime)

    # ============================
    # STRIKE DISTANCE CHECK
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
    # MAX LOSS / CAPITAL RISK
    # ============================
    width = abs(short_strike - long_strike)
    max_loss = width * lot_size * lots
    metrics["max_loss"] = max_loss

    if capital <= 0:
        return (
            False,
            "Capital not available",
            metrics,
        )

    risk_pct = (max_loss / capital) * 100.0
    metrics["risk_pct_capital"] = risk_pct

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
