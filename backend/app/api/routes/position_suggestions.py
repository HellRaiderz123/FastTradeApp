"""
Smart Position Suggestions API
-------------------------------
Compares open positions against live TA signals and returns actionable
suggestions: HOLD / CONSIDER_EXIT / HEDGE_SUGGESTED / WATCH.

Handles two types of positions:
1. App-originated positions with proper strategy (e.g. BULL_PUT, IRON_CONDOR)
2. Zerodha-synced positions (DIRECT_ZERODHA) — detects spread type first
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent
from app.core.position_advisor import advise_position
from app.core.spreads import detect_spreads

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/positions", tags=["Positions"])

# Map spread-detection names → strategy-engine names
_SPREAD_TO_STRATEGY: Dict[str, str] = {
    "BULL_PUT_SPREAD": "BULL_PUT",
    "BULL_CALL_SPREAD": "BULL_CALL",
    "BEAR_CALL_SPREAD": "BEAR_CALL",
    "BEAR_PUT_SPREAD": "BEAR_PUT",
    "IRON_CONDOR": "IRON_CONDOR",
    "SHORT_STRADDLE": "SHORT_STRADDLE",
    "LONG_STRADDLE": "LONG_STRADDLE",
    "SHORT_STRANGLE": "SHORT_STRANGLE",
    "LONG_STRANGLE": "LONG_STRANGLE",
    "BUTTERFLY_CALL": "BUTTERFLY_SPREAD",
    "BUTTERFLY_PUT": "BUTTERFLY_SPREAD",
    "RATIO_CALL_BACKSPREAD": "CALL_RATIO_BACKSPREAD",
    "RATIO_PUT_BACKSPREAD": "PUT_RATIO_BACKSPREAD",
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/smart-suggestions")
def get_smart_suggestions(db: Session = Depends(get_db)):
    """
    For every open position, run the TA engine and compare the current
    signal against the position's strategy.  Returns per-position advice.

    Handles both app-originated and Zerodha-synced positions by using
    spread detection to identify what strategy the positions form.

    Response shape:
    {
        "suggestions": {
            "<intent_id>": { ... advice ... }
        },
        "spread_suggestions": [
            { "spread_type": "BULL_PUT_SPREAD", "underlying": "NIFTY", "intent_ids": [...], "advice": { ... } }
        ],
        "has_warnings": true,
        "critical_count": 1
    }
    """
    # 1) Fetch all open (EXECUTED, not closed) positions
    intents: List[ExecutionIntent] = (
        db.query(ExecutionIntent)
        .filter(
            ExecutionIntent.status == "EXECUTED",
            ExecutionIntent.closed_at.is_(None),
        )
        .all()
    )

    if not intents:
        return {
            "suggestions": {},
            "spread_suggestions": [],
            "has_warnings": False,
            "critical_count": 0,
        }

    suggestions: Dict[str, Any] = {}
    spread_suggestions: List[Dict[str, Any]] = []

    # ── A) Handle app-originated positions with known strategy ──
    app_intents = [i for i in intents if (i.strategy or "") not in ("DIRECT_ZERODHA", "CUSTOM", "")]
    for intent in app_intents:
        strategy = intent.strategy or ""
        underlying = intent.underlying or ""
        intent_id = intent.intent_id or ""
        pnl = float(intent.pnl or 0)
        entry_credit = float(intent.entry_credit or 0)

        try:
            advice = advise_position(
                strategy=strategy,
                underlying=underlying,
                db=db,
                pnl=pnl,
                entry_credit=entry_credit,
            )
            suggestions[intent_id] = advice
        except Exception as e:
            logger.warning(f"Smart suggestion failed for {intent_id}: {e}")
            suggestions[intent_id] = {
                "action": "HOLD",
                "severity": "NONE",
                "reason": "Could not evaluate — defaulting to HOLD",
                "details": str(e),
            }

    # ── B) Handle Zerodha-synced positions via spread detection ──
    zerodha_intents = [i for i in intents if (i.strategy or "") in ("DIRECT_ZERODHA", "CUSTOM")]
    if zerodha_intents:
        # Convert to dicts for the spread detector
        intent_dicts = [
            {
                "intent_id": i.intent_id,
                "strategy": i.strategy,
                "underlying": i.underlying,
                "expiry": i.expiry,
                "ticket": i.ticket or {},
                "pnl": i.pnl,
                "unrealized_pnl": i.unrealized_pnl,
                "entry_credit": i.entry_credit,
            }
            for i in zerodha_intents
        ]

        try:
            grouped = detect_spreads(intent_dicts)

            for spread in grouped.spreads:
                spread_type = spread.spread_type
                underlying = spread.underlying or ""
                strategy_name = _SPREAD_TO_STRATEGY.get(spread_type, "")

                if not strategy_name or not underlying:
                    continue

                # Compute combined P&L across all legs of this spread
                combined_pnl = sum(
                    float(leg.pnl or 0) for leg in spread.legs
                )
                combined_credit = sum(
                    float(leg.entry_credit or 0) for leg in spread.legs
                )
                leg_intent_ids = list(set(leg.intent_id for leg in spread.legs))

                try:
                    advice = advise_position(
                        strategy=strategy_name,
                        underlying=underlying,
                        db=db,
                        pnl=combined_pnl,
                        entry_credit=combined_credit,
                    )

                    spread_entry = {
                        "spread_type": spread_type,
                        "strategy": strategy_name,
                        "underlying": underlying,
                        "intent_ids": leg_intent_ids,
                        "advice": advice,
                    }
                    spread_suggestions.append(spread_entry)

                    # Also assign to each member intent_id so the frontend can match
                    for iid in leg_intent_ids:
                        suggestions[iid] = advice

                except Exception as e:
                    logger.warning(f"Smart suggestion failed for spread {spread_type} ({underlying}): {e}")

            # Naked positions — skip (no strategy to evaluate)
            for naked in grouped.naked_positions:
                logger.debug(f"Skipping naked position: {naked.intent_id}")

        except Exception as e:
            logger.warning(f"Spread detection failed for Zerodha positions: {e}")

    has_warnings = any(
        s.get("severity") in ("HIGH", "MEDIUM") for s in suggestions.values()
    )
    critical_count = sum(
        1 for s in suggestions.values() if s.get("severity") == "HIGH"
    )

    return {
        "suggestions": suggestions,
        "spread_suggestions": spread_suggestions,
        "has_warnings": has_warnings,
        "critical_count": critical_count,
    }

