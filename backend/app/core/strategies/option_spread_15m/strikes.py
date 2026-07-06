"""
strikes.py
----------
Strike selection logic for 15m option spreads.
Pure calculation, no IO, no broker calls.
"""

from typing import Tuple, Dict, TypedDict


class SpreadStrikes(TypedDict):
    bull: Tuple[int, int]
    bear: Tuple[int, int]
    # (short_put, long_put, short_call, long_call)
    condor: Tuple[int, int, int, int]
    # Straddle/Strangle: (call_strike, put_strike)
    straddle: Tuple[int, int]
    strangle: Tuple[int, int]
    # Butterfly: (lower, middle, upper)
    butterfly_call: Tuple[int, int, int]
    butterfly_put: Tuple[int, int, int]
    # Ratio Backspreads: (short_strike, long_strike_near, long_strike_far)
    call_ratio_backspread: Tuple[int, int, int]
    put_ratio_backspread: Tuple[int, int, int]
    meta: Dict[str, int]


def get_step(underlying: str) -> int:
    """
    Strike step based on underlying.
    """
    return 50 if underlying == "NIFTY" else 100


def compute_spread_strikes(
    *,
    underlying: str,
    spot: float,
    atm: int,
    risk_mode: str,
    iv_regime: str,
    recommendation: str,
) -> SpreadStrikes:
    """
    Compute strikes for Bull Put and Bear Call spreads.
    """

    step = get_step(underlying)

    # ============================
    # BASE WIDTH (risk mode)
    # ============================
    width = step * (2 if risk_mode == "Conservative" else 1)

    # ============================
    # MINIMUM ATM DISTANCE (at least 1% OTM)
    # ============================
    min_atm_dist_map = {
        "LOW": 1.0,
        "NORMAL": 1.0,
        "HIGH": 1.2,
    }
    min_atm_dist_pct = min_atm_dist_map.get(iv_regime, 1.0)
    
    # Calculate minimum offset in rupees (at least 1% of spot)
    min_offset_rupees = spot * (min_atm_dist_pct / 100.0)
    min_offset_steps = max(1, int(round(min_offset_rupees / step)))
    min_offset = min_offset_steps * step

    # Always enforce minimum 1% OTM distance
    short_offset = max(min_offset, step * 2) if risk_mode == "Conservative" else min_offset

    # ============================
    # LOW IV → FAR OTM LOGIC
    # ============================
    if iv_regime == "LOW":
        target_dist_pct = 1.0 if recommendation == "NO_TRADE" else 0.7

        try:
            target_offset = int(
                round((spot * target_dist_pct / 100) / step)
            ) * step
        except Exception:
            target_offset = step * 2

        short_offset = max(short_offset, step * 2, target_offset)
        width = max(width, step * 2)
    else:
        # Ensure minimum distance for NORMAL and HIGH IV
        short_offset = max(short_offset, min_offset)

    # ============================
    # BULL PUT
    # ============================
    bull_short = atm - short_offset
    bull_long = bull_short - width
    if bull_long >= bull_short:
        bull_long = bull_short - width

    # ============================
    # BEAR CALL
    # ============================
    bear_short = atm + short_offset
    bear_long = bear_short + width
    if bear_long <= bear_short:
        bear_long = bear_short + width

    # ============================
    # IRON CONDOR (same offsets/width)
    # ============================
    condor_short_put = bull_short
    condor_long_put = bull_long
    condor_short_call = bear_short
    condor_long_call = bear_long

    # ============================
    # STRADDLE (ATM both sides)
    # ============================
    straddle_call = atm
    straddle_put = atm

    # ============================
    # STRANGLE (OTM both sides)
    # ============================
    strangle_call = atm + step
    strangle_put = atm - step

    # ============================
    # BUTTERFLY (Call or Put)
    # ============================
    # Buy 1 ITM, Sell 2 ATM, Buy 1 OTM
    butterfly_lower = atm - width
    butterfly_middle = atm
    butterfly_upper = atm + width

    # ============================
    # CALL RATIO BACKSPREAD
    # ============================
    # Sell 1 ITM call, Buy 2 OTM calls
    # Short strike slightly ITM, Long strikes OTM
    call_ratio_short = atm - step  # Slightly ITM
    call_ratio_long_near = atm + step  # OTM
    call_ratio_long_far = atm + (step * 2)  # Further OTM

    # ============================
    # PUT RATIO BACKSPREAD
    # ============================
    # Sell 1 ITM put, Buy 2 OTM puts
    put_ratio_short = atm + step  # Slightly ITM
    put_ratio_long_near = atm - step  # OTM
    put_ratio_long_far = atm - (step * 2)  # Further OTM

    return {
        "bull": (bull_short, bull_long),
        "bear": (bear_short, bear_long),
        "condor": (condor_short_put, condor_long_put, condor_short_call, condor_long_call),
        "straddle": (straddle_call, straddle_put),
        "strangle": (strangle_call, strangle_put),
        "butterfly_call": (butterfly_lower, butterfly_middle, butterfly_upper),
        "butterfly_put": (butterfly_lower, butterfly_middle, butterfly_upper),
        "call_ratio_backspread": (call_ratio_short, call_ratio_long_near, call_ratio_long_far),
        "put_ratio_backspread": (put_ratio_short, put_ratio_long_near, put_ratio_long_far),
        "meta": {
            "step": step,
            "width": width,
            "short_offset": short_offset,
        },
    }
