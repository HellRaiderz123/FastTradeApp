"""
broker_reconcile.py
--------------------
Detects positions that were closed directly on Zerodha (broker side)
and marks them as CLOSED in the local database.

Without this, positions closed via the Zerodha app/terminal stay stuck
as EXECUTED in FastTradeApp forever.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Set

from sqlalchemy.orm import Session

from app.core.utils.time import now_ist
from app.db.models_intent import ExecutionIntent
from app.core.broker.zerodha.client import get_kite_client
from app.core.learning.signal_diagnostics import record_exit_outcome

logger = logging.getLogger(__name__)

# Throttle: only reconcile every N seconds (avoids hammering Kite API)
_RECONCILE_INTERVAL = 30  # seconds
_last_reconcile_ts: float = 0.0


def reconcile_broker_positions(db: Session, force: bool = False) -> List[str]:
    """
    Compare local EXECUTED intents against Zerodha's live net positions.
    Any intent whose legs are all quantity-0 at the broker gets marked CLOSED.

    Args:
        db: Active database session.
        force: Skip time-based throttle.

    Returns:
        List of intent_ids that were closed by reconciliation.
    """
    import time

    global _last_reconcile_ts
    now = time.time()
    if not force and (now - _last_reconcile_ts < _RECONCILE_INTERVAL):
        return []
    _last_reconcile_ts = now

    # ── 1. Fetch broker positions ────────────────────────────────
    try:
        kite = get_kite_client()
        broker_positions = kite.positions()
    except Exception as e:
        logger.debug("Broker reconcile skipped — Kite unavailable: %s", e)
        return []

    net = broker_positions.get("net", [])

    # Build a map: symbol → net quantity (and last_price for final PnL)
    broker_map: Dict[str, dict] = {}
    for pos in net:
        sym = (pos.get("tradingsymbol") or "").strip()
        if sym:
            broker_map[sym] = {
                "quantity": pos.get("quantity", 0),
                "last_price": pos.get("last_price", 0),
                "pnl": pos.get("m2m", pos.get("pnl", 0)),
            }

    # If broker returned nothing at all, skip reconciliation — could be a transient error
    if not broker_map and not net:
        # Empty net positions list means no open positions at all at broker
        # This is valid — mark all Zerodha intents as closed
        pass

    # ── 2. Find local EXECUTED intents with Zerodha mode ─────────
    open_intents = (
        db.query(ExecutionIntent)
        .filter(
            ExecutionIntent.status == "EXECUTED",
            ExecutionIntent.closed_at.is_(None),
        )
        .all()
    )

    closed_ids: List[str] = []

    for intent in open_intents:
        # Only reconcile actual LIVE Zerodha positions
        # Skip PAPER and DRY_RUN — they have no real broker legs
        mode = ""
        exec_result = intent.execution_result or {}
        if isinstance(exec_result, str):
            import json as _json
            try:
                exec_result = _json.loads(exec_result)
            except Exception:
                exec_result = {}
        if isinstance(exec_result, dict):
            mode = str(exec_result.get("mode", "")).upper()
        if "ZERODHA" not in mode:
            continue
        # DRY_RUN positions have no real broker legs — reconcile would
        # incorrectly close them because Kite has no matching symbols.
        if "DRY_RUN" in mode or "PAPER" in mode:
            continue
        # Holdings and direct synced trades are not app-executed — skip
        if intent.strategy in ("ZERODHA_HOLDING", "ZERODHA_ACTUAL", "DIRECT_ZERODHA"):
            continue

        import json as _json
        ticket = intent.ticket_dict
        legs = ticket.get("legs", [])
        if not legs:
            continue

        # Check if ALL leg symbols have zero quantity at broker
        all_closed = True
        total_broker_pnl = 0.0
        for leg in legs:
            sym = leg.get("symbol", "")
            if not sym:
                # No symbol stored — can't verify, assume still open
                all_closed = False
                break

            broker_info = broker_map.get(sym)
            if broker_info is None:
                # Symbol not in broker positions at all → it's closed (quantity 0)
                continue
            if broker_info["quantity"] != 0:
                # Still has open quantity at broker → not closed
                all_closed = False
                break
            total_broker_pnl += broker_info.get("pnl", 0)

        if not all_closed:
            continue

        # ── Mark as CLOSED ───────────────────────────────────────
        logger.info(
            "🔄 Broker reconcile: closing %s (%s %s) — all legs squared off at Zerodha",
            intent.intent_id, intent.strategy, intent.underlying,
        )

        intent.status = "CLOSED"  # type: ignore
        intent.closed_at = now_ist()  # type: ignore
        intent.exit_reason = "BROKER_CLOSED"  # type: ignore

        # Always write broker-reported P&L (including 0) so closed entries are accurate
        intent.pnl = total_broker_pnl  # type: ignore

        try:
            record_exit_outcome(db, intent=intent, commit=False)
        except Exception:
            pass

        closed_ids.append(intent.intent_id)

    if closed_ids:
        try:
            db.commit()
            logger.info("✅ Broker reconcile: closed %d stale positions: %s", len(closed_ids), closed_ids)
        except Exception as e:
            db.rollback()
            logger.error("❌ Broker reconcile commit failed: %s", e)
            return []

    return closed_ids
