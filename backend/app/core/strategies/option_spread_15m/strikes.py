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

    # Conservative default: slightly OTM
    short_offset = step if risk_mode == "Conservative" else 0

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

    return {
        "bull": (bull_short, bull_long),
        "bear": (bear_short, bear_long),
        "meta": {
            "step": step,
            "width": width,
            "short_offset": short_offset,
        },
    }
