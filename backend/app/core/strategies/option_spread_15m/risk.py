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


def check_condor_risk(
    *,
    short_put: int,
    long_put: int,
    short_call: int,
    long_call: int,
    spot: float,
    capital: float,
    lot_size: int,
    lots: int,
    iv_regime: str,
    risk_config: Optional[RiskLimits] = None,
) -> Tuple[bool, str, Dict[str, float]]:
    """Hard risk gates for iron condor.

    Notes:
    - Computes worst-case max loss using the wider wing.
    - Requires both short legs to be at least min distance from ATM.
    """

    metrics: Dict[str, float] = {}
    limits = get_risk_limits(iv_regime, risk_config)

    put_width = abs(short_put - long_put)
    call_width = abs(long_call - short_call)
    wing_width = max(put_width, call_width)

    metrics["put_width"] = float(put_width)
    metrics["call_width"] = float(call_width)
    metrics["wing_width"] = float(wing_width)

    max_loss = wing_width * lot_size * lots
    metrics["max_loss"] = float(max_loss)

    if capital > 0:
        risk_pct = (max_loss / capital) * 100.0
    else:
        risk_pct = float("inf")

    metrics["risk_pct_capital"] = float(risk_pct)

    short_put_dist = pct_from_atm(short_put, spot)
    short_call_dist = pct_from_atm(short_call, spot)
    metrics["short_put_dist_pct"] = float(short_put_dist)
    metrics["short_call_dist_pct"] = float(short_call_dist)

    if short_put_dist < limits["min_atm_dist_pct"]:
        return (
            False,
            f"Put strike too close to ATM ({short_put_dist:.2f}% < {limits['min_atm_dist_pct']}%)",
            metrics,
        )

    if short_call_dist < limits["min_atm_dist_pct"]:
        return (
            False,
            f"Call strike too close to ATM ({short_call_dist:.2f}% < {limits['min_atm_dist_pct']}%)",
            metrics,
        )

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

    return True, "Risk within limits", metrics


def check_straddle_strangle_risk(
    *,
    call_strike: int,
    put_strike: int,
    spot: float,
    capital: float,
    lot_size: int,
    lots: int,
    iv_regime: str,
    is_short: bool,  # True for short straddle/strangle, False for long
    risk_config: Optional[RiskLimits] = None,
) -> Tuple[bool, str, Dict[str, float]]:
    """
    Risk check for straddle/strangle strategies.
    
    Short straddle/strangle: Unlimited risk (use high capital % limit)
    Long straddle/strangle: Limited risk (max loss = premium paid, estimated as 5% of notional)
    """
    
    metrics: Dict[str, float] = {}
    limits = get_risk_limits(iv_regime, risk_config)
    
    if is_short:
        # Short straddle/strangle: unlimited risk on both sides
        # Use conservative estimate: 10% move from each strike
        estimated_move_pct = 10.0
        call_loss_estimate = call_strike * (estimated_move_pct / 100) * lot_size * lots
        put_loss_estimate = put_strike * (estimated_move_pct / 100) * lot_size * lots
        max_loss = max(call_loss_estimate, put_loss_estimate)
        
        metrics["max_loss"] = max_loss
        metrics["risk_type"] = "UNLIMITED"
        
        # Require strikes be reasonably far from ATM for short positions
        call_dist = pct_from_atm(call_strike, spot)
        put_dist = pct_from_atm(put_strike, spot)
        
        metrics["call_dist_pct"] = call_dist
        metrics["put_dist_pct"] = put_dist
        
        # For straddle (ATM), we need higher confidence; check via other means
        # For strangle, enforce minimum distance
        if call_strike != put_strike:  # Strangle case
            min_dist = limits["min_atm_dist_pct"]
            if call_dist < min_dist or put_dist < min_dist:
                return (
                    False,
                    f"Strikes too close to ATM for short strangle (min {min_dist}%)",
                    metrics,
                )
    else:
        # Long straddle/strangle: limited risk = premium paid
        # Rough estimate: 5% of notional per leg
        premium_estimate_pct = 5.0
        notional_call = call_strike * lot_size * lots
        notional_put = put_strike * lot_size * lots
        premium_estimate = (notional_call + notional_put) * (premium_estimate_pct / 100)
        
        max_loss = premium_estimate
        metrics["max_loss"] = max_loss
        metrics["risk_type"] = "LIMITED"
    
    if capital <= 0:
        return (False, "Capital not available", metrics)
    
    risk_pct = (max_loss / capital) * 100.0
    metrics["risk_pct_capital"] = risk_pct
    
    # For short positions, use stricter limit (2x normal)
    max_allowed = limits["max_risk_pct_capital"] * (2 if is_short else 1)
    
    if risk_pct > max_allowed:
        return (
            False,
            f"Risk {risk_pct:.2f}% exceeds limit {max_allowed:.2f}%",
            metrics,
        )
    
    return True, "Risk within limits", metrics


def check_butterfly_risk(
    *,
    lower_strike: int,
    middle_strike: int,
    upper_strike: int,
    spot: float,
    capital: float,
    lot_size: int,
    lots: int,
    iv_regime: str,
    risk_config: Optional[RiskLimits] = None,
) -> Tuple[bool, str, Dict[str, float]]:
    """
    Risk check for butterfly spread (limited risk debit spread).
    
    Max loss = Net debit paid (estimated)
    Max profit = (Middle - Lower) - Net debit
    """
    
    metrics: Dict[str, float] = {}
    limits = get_risk_limits(iv_regime, risk_config)
    
    # Butterfly structure: Buy 1 lower, Sell 2 middle, Buy 1 upper
    wing_width = middle_strike - lower_strike
    
    # Max loss estimate: 30% of wing width as net debit (conservative)
    debit_estimate_pct = 30.0
    max_loss = wing_width * (debit_estimate_pct / 100) * lot_size * lots
    
    metrics["max_loss"] = max_loss
    metrics["wing_width"] = wing_width
    metrics["risk_type"] = "LIMITED"
    
    if capital <= 0:
        return (False, "Capital not available", metrics)
    
    risk_pct = (max_loss / capital) * 100.0
    metrics["risk_pct_capital"] = risk_pct
    
    if risk_pct > limits["max_risk_pct_capital"]:
        return (
            False,
            f"Risk {risk_pct:.2f}% exceeds limit {limits['max_risk_pct_capital']}%",
            metrics,
        )
    
    return True, "Risk within limits", metrics


def check_ratio_backspread_risk(
    *,
    short_strike: int,
    long_strike_near: int,
    long_strike_far: int,
    spot: float,
    capital: float,
    lot_size: int,
    lots: int,
    iv_regime: str,
    is_call: bool,  # True for call ratio backspread, False for put
    risk_config: Optional[RiskLimits] = None,
) -> Tuple[bool, str, Dict[str, float]]:
    """
    Risk check for ratio backspread (1 short, 2 long).
    
    Max loss occurs between strikes (limited).
    Max profit is unlimited in the favorable direction.
    """
    
    metrics: Dict[str, float] = {}
    limits = get_risk_limits(iv_regime, risk_config)
    
    # Ratio backspread: Sell 1, Buy 2
    # Max loss between short and long strikes
    spread_width = abs(long_strike_near - short_strike)
    
    # Max loss = spread width - net credit (estimate credit as 20% of spread)
    credit_estimate_pct = 20.0
    credit_estimate = spread_width * (credit_estimate_pct / 100) * lot_size * lots
    max_loss = (spread_width * lot_size * lots) - credit_estimate
    
    metrics["max_loss"] = max_loss
    metrics["spread_width"] = spread_width
    metrics["risk_type"] = "LIMITED"
    
    # Check that long strikes are sufficiently OTM
    if is_call:
        # For call ratio: long strikes should be above spot
        if long_strike_near <= spot or long_strike_far <= spot:
            return (
                False,
                "Long call strikes must be OTM (above spot)",
                metrics,
            )
    else:
        # For put ratio: long strikes should be below spot
        if long_strike_near >= spot or long_strike_far >= spot:
            return (
                False,
                "Long put strikes must be OTM (below spot)",
                metrics,
            )
    
    if capital <= 0:
        return (False, "Capital not available", metrics)
    
    risk_pct = (max_loss / capital) * 100.0
    metrics["risk_pct_capital"] = risk_pct
    
    if risk_pct > limits["max_risk_pct_capital"]:
        return (
            False,
            f"Risk {risk_pct:.2f}% exceeds limit {limits['max_risk_pct_capital']}%",
            metrics,
        )
    
    return True, "Risk within limits", metrics
