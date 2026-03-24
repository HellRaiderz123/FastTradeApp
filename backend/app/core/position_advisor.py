"""
position_advisor.py
--------------------
Smart Position Advisor — compares open positions against live TA signals
and generates actionable suggestions (HOLD / EXIT / HEDGE / WATCH).

When you took a Bull Put Spread but the TA engine now says BEARISH,
this module will flag it and suggest you consider exiting or hedging.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.core.signals.signals import generate_signal
from app.core.strategies.option_spread_15m.context import build_market_context
from app.core.strategies.option_spread_15m.decision import decide_strategy
from app.core.strategies.option_spread_15m.strategy_definitions import (
    STRATEGY_CONFIGS,
    StrategyType,
)

logger = logging.getLogger(__name__)


# ─── Strategy bias lookup ────────────────────────────────────────────
STRATEGY_BIAS: Dict[str, str] = {}
for _st, _cfg in STRATEGY_CONFIGS.items():
    STRATEGY_BIAS[_st.value] = _cfg.bias

# Friendly names
STRATEGY_NAMES: Dict[str, str] = {}
for _st, _cfg in STRATEGY_CONFIGS.items():
    STRATEGY_NAMES[_st.value] = _cfg.name


def _bias_of(strategy: str) -> str:
    """Return BULLISH / BEARISH / NEUTRAL for a strategy name."""
    return STRATEGY_BIAS.get(strategy, "NEUTRAL")


def _name_of(strategy: str) -> str:
    return STRATEGY_NAMES.get(strategy, strategy.replace("_", " ").title())


# ─── Conflict detection ─────────────────────────────────────────────

def _are_biases_conflicting(position_bias: str, signal_bias: str) -> bool:
    """Check if position bias and signal bias are in direct conflict."""
    conflicts = {
        ("BULLISH", "BEARISH"),
        ("BEARISH", "BULLISH"),
    }
    return (position_bias, signal_bias) in conflicts


def _severity(position_bias: str, signal_bias: str, confidence: float) -> str:
    """
    Determine severity of the mismatch.
    HIGH   = direct conflict (bull vs bear) with high confidence
    MEDIUM = direct conflict with moderate confidence, or neutral shift
    LOW    = minor drift or low confidence
    """
    if _are_biases_conflicting(position_bias, signal_bias):
        if confidence >= 70:
            return "HIGH"
        if confidence >= 55:
            return "MEDIUM"
        return "LOW"

    # Position is directional but signal is NEUTRAL
    if position_bias != "NEUTRAL" and signal_bias == "NEUTRAL":
        if confidence >= 65:
            return "MEDIUM"
        return "LOW"

    return "LOW"


# ─── Main advisor logic ─────────────────────────────────────────────

def advise_position(
    strategy: str,
    underlying: str,
    db,
    pnl: float = 0.0,
    entry_credit: float = 0.0,
    min_confidence: float = 60,
) -> Dict[str, Any]:
    """
    Evaluate a single open position against the current TA signal.

    Returns a dict:
        {
            action: "HOLD" | "CONSIDER_EXIT" | "HEDGE_SUGGESTED" | "WATCH",
            severity: "HIGH" | "MEDIUM" | "LOW" | "NONE",
            reason: str,
            details: str,
            position_bias: str,
            current_signal_bias: str,
            current_strategy_suggestion: str,
            current_confidence: float,
            current_market_mode: str,
            current_iv_regime: str,
        }
    """

    position_bias = _bias_of(strategy)
    position_name = _name_of(strategy)

    # ── Fetch live TA signal ──────────────────────────────────
    try:
        sig = generate_signal(db=db, symbol=underlying, use_ml=False)
    except Exception as e:
        logger.warning(f"Smart advisor: signal generation failed for {underlying}: {e}")
        return _hold_result(strategy, position_bias, reason="Signal unavailable")

    confidence = float(sig.get("confidence", 0))
    signal_bias = sig.get("bias", "NEUTRAL")
    ctx = build_market_context(sig)

    # ── What would the engine suggest NOW? ────────────────────
    new_strategy, new_reason = decide_strategy(
        sig=sig,
        ctx=ctx,
        confidence=confidence,
        min_confidence=min_confidence,
    )

    new_bias = _bias_of(new_strategy) if new_strategy != "NO_TRADE" else signal_bias
    new_name = _name_of(new_strategy)

    market_mode = ctx.get("market_mode", "UNKNOWN")
    iv_regime = ctx.get("iv_regime", "UNKNOWN")

    base = {
        "position_bias": position_bias,
        "position_strategy_name": position_name,
        "current_signal_bias": signal_bias,
        "current_strategy_suggestion": new_strategy,
        "current_strategy_name": new_name,
        "current_confidence": round(confidence, 1),
        "current_market_mode": market_mode,
        "current_iv_regime": iv_regime,
    }

    # ── Same strategy → HOLD ─────────────────────────────────
    if new_strategy == strategy:
        return {
            **base,
            "action": "HOLD",
            "severity": "NONE",
            "reason": f"TA still favours {position_name}",
            "details": f"Signal: {signal_bias} ({confidence:.0f}% confidence). Market is {market_mode}, IV {iv_regime}. No change needed.",
        }

    # ── Engine says NO_TRADE now ──────────────────────────────
    if new_strategy == "NO_TRADE":
        # Neutral strategies do not depend on directional bias - only exit via TP/SL
        if strategy in ("IRON_CONDOR", "BUTTERFLY_SPREAD", "SHORT_STRANGLE", "SHORT_STRADDLE", "LONG_STRANGLE"):
            return {
                **base,
                "action": "WATCH",
                "severity": "LOW",
                "reason": f"TA says NO_TRADE but {position_name} is direction-neutral - let TP/SL manage exit",
                "details": f"Neutral strategy held. conf={confidence:.0f}%, market={market_mode}, IV={iv_regime}.",
            }
        # If position is in profit, suggest taking profits (HIGH severity)
        if pnl > 0 and entry_credit > 0 and (pnl / abs(entry_credit)) > 0.5:
            return {
                **base,
                "action": "CONSIDER_EXIT",
                "severity": "HIGH",
                "reason": f"TA no longer supports any trade — you're in profit, consider booking",
                "details": (
                    f"Your {position_name} is in ₹{pnl:,.0f} profit. "
                    f"Signal quality dropped (conf={confidence:.0f}%, bias={signal_bias}). "
                    f"No new strategy passes quality gates. Consider booking profits."
                ),
            }
        # Strategy completely changed to NO_TRADE — this is a clear signal to exit
        # Use MEDIUM severity minimum so auto-trader can act on it
        sev = "HIGH" if confidence >= 65 else "MEDIUM"
        return {
            **base,
            "action": "CONSIDER_EXIT",
            "severity": sev,
            "reason": f"TA engine says NO_TRADE — strategy conditions no longer valid",
            "details": (
                f"Your {position_name} ({position_bias}) is still open but the TA engine "
                f"no longer recommends any strategy (quality/confidence too low). "
                f"Current: {signal_bias} bias, {confidence:.0f}% confidence, {market_mode} market. "
                f"Strategy conditions have changed — consider exiting to avoid risk."
            ),
        }

    # ── Direct bias conflict ──────────────────────────────────
    sev = _severity(position_bias, new_bias, confidence)

    if _are_biases_conflicting(position_bias, new_bias):
        # HIGH severity = strong conviction opposite direction
        if sev == "HIGH":
            return {
                **base,
                "action": "CONSIDER_EXIT",
                "severity": "HIGH",
                "reason": f"⚠️ CONFLICT: You have {position_name} ({position_bias}) but TA now says {new_name} ({new_bias})",
                "details": (
                    f"CRITICAL: Your position is {position_bias} but the market has shifted to {new_bias} "
                    f"with {confidence:.0f}% confidence. TA engine now recommends {new_name}. "
                    f"Market: {market_mode}, IV: {iv_regime}. "
                    f"Strongly consider exiting to limit losses, or add a hedge."
                ),
            }
        else:
            return {
                **base,
                "action": "HEDGE_SUGGESTED",
                "severity": sev,
                "reason": f"Bias shifted: {position_bias} → {new_bias} (moderate confidence)",
                "details": (
                    f"Your {position_name} ({position_bias}) faces opposing signal: {new_name} ({new_bias}). "
                    f"Confidence is moderate ({confidence:.0f}%), so hedging may be better than a full exit. "
                    f"Market: {market_mode}, IV: {iv_regime}."
                ),
            }

    # ── Same bias but different strategy (e.g. BULL_PUT → CALL_RATIO) ─
    if new_bias == position_bias and new_strategy != strategy:
        return {
            **base,
            "action": "HOLD",
            "severity": "LOW",
            "reason": f"TA suggests {new_name} instead, but both are {position_bias} — HOLD",
            "details": (
                f"TA now prefers {new_name} over your {position_name}, but both are {position_bias}. "
                f"No bias conflict. Your position is still aligned with the market direction. "
                f"Signal: {confidence:.0f}% confidence, {market_mode} market."
            ),
        }

    # ── Neutral shift (your directional bet, market now neutral) ──
    if new_bias == "NEUTRAL" and position_bias != "NEUTRAL":
        return {
            **base,
            "action": "WATCH",
            "severity": sev,
            "reason": f"Market turned neutral — your {position_bias} position may stall",
            "details": (
                f"TA suggests {new_name} (NEUTRAL) while you hold {position_name} ({position_bias}). "
                f"Your directional bet may not pay off if the market stays range-bound. "
                f"Confidence: {confidence:.0f}%. Consider tightening stop-loss or partial exit."
            ),
        }

    # ── Position is NEUTRAL but market turned directional ─────
    if position_bias == "NEUTRAL" and new_bias != "NEUTRAL":
        return {
            **base,
            "action": "WATCH",
            "severity": sev,
            "reason": f"Market turned {new_bias} — risky for your neutral {position_name}",
            "details": (
                f"You hold a neutral strategy ({position_name}) but TA now sees {new_bias} bias "
                f"({new_name}, conf={confidence:.0f}%). A directional move could hurt a neutral position. "
                f"Monitor breakeven levels closely."
            ),
        }

    # ── Fallback ─────────────────────────────────────────────
    return {
        **base,
        "action": "HOLD",
        "severity": "LOW",
        "reason": f"Minor strategy drift: {position_name} → {new_name}",
        "details": (
            f"TA now prefers {new_name} but your {position_name} is not in direct conflict. "
            f"Signal: {signal_bias}, {confidence:.0f}% confidence, {market_mode} market."
        ),
    }


def _hold_result(strategy: str, position_bias: str, reason: str = "") -> Dict[str, Any]:
    return {
        "action": "HOLD",
        "severity": "NONE",
        "reason": reason or f"No signal data — defaulting to HOLD",
        "details": "Could not evaluate signal. No action recommended.",
        "position_bias": position_bias,
        "position_strategy_name": _name_of(strategy),
        "current_signal_bias": "UNKNOWN",
        "current_strategy_suggestion": "UNKNOWN",
        "current_strategy_name": "Unknown",
        "current_confidence": 0,
        "current_market_mode": "UNKNOWN",
        "current_iv_regime": "UNKNOWN",
    }


# ─── Batch advisor for all open positions ────────────────────────────

def advise_all_positions(
    positions: List[Dict[str, Any]],
    db,
    min_confidence: float = 60,
) -> Dict[str, Dict[str, Any]]:
    """
    Evaluate all open positions and return a dict keyed by intent_id.

    Each position dict must have: intent_id, strategy, underlying, pnl, entry_credit.
    """
    results: Dict[str, Dict[str, Any]] = {}

    # Group by underlying to avoid duplicate signal fetches
    by_underlying: Dict[str, List[Dict[str, Any]]] = {}
    for pos in positions:
        und = pos.get("underlying", "")
        if und not in by_underlying:
            by_underlying[und] = []
        by_underlying[und].append(pos)

    # Cache signal per underlying
    signal_cache: Dict[str, Dict[str, Any]] = {}

    for underlying, group in by_underlying.items():
        # Fetch signal once per underlying
        try:
            sig = generate_signal(db=db, symbol=underlying, use_ml=False)
            signal_cache[underlying] = sig
        except Exception as e:
            logger.warning(f"Smart advisor: signal failed for {underlying}: {e}")
            sig = None

        for pos in group:
            intent_id = pos.get("intent_id", "")
            strategy = pos.get("strategy", "")
            pnl = float(pos.get("pnl", 0) or 0)
            entry_credit = float(pos.get("entry_credit", 0) or 0)

            if sig is None:
                results[intent_id] = _hold_result(strategy, _bias_of(strategy), "Signal unavailable")
                continue

            confidence = float(sig.get("confidence", 0))
            ctx = build_market_context(sig)
            new_strategy, new_reason = decide_strategy(
                sig=sig, ctx=ctx,
                confidence=confidence,
                min_confidence=min_confidence,
            )

            # Reuse the per-position logic but with cached signal
            results[intent_id] = advise_position(
                strategy=strategy,
                underlying=underlying,
                db=db,
                pnl=pnl,
                entry_credit=entry_credit,
                min_confidence=min_confidence,
            )

    return results
