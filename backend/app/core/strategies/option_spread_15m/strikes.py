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
    # MINIMUM ATM DISTANCE (from risk limits)
    # ============================
    min_atm_dist_map = {
        "LOW": 0.5,
        "NORMAL": 0.6,
        "HIGH": 0.8,
    }
    min_atm_dist_pct = min_atm_dist_map.get(iv_regime, 0.6)
    
    # Calculate minimum offset in rupees
    min_offset_rupees = spot * (min_atm_dist_pct / 100.0)
    min_offset_steps = max(1, int(round(min_offset_rupees / step)))
    min_offset = min_offset_steps * step

    # Conservative default: slightly OTM
    short_offset = step if risk_mode == "Conservative" else min_offset

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

    return {
        "bull": (bull_short, bull_long),
        "bear": (bear_short, bear_long),
        "condor": (condor_short_put, condor_long_put, condor_short_call, condor_long_call),
        "meta": {
            "step": step,
            "width": width,
            "short_offset": short_offset,
        },
    }
