from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.execution.paper import PaperExecutionAdapter
from app.core.execution.zerodha import ZerodhaExecutionAdapter
from app.core.broker.zerodha.client import get_kite_client
from app.core.utils.time import now_ist
from app.db.models_intent import ExecutionIntent
from app.db.session import SessionLocal
from app.services.zerodha_ticker import get_cached_ltp as get_ticker_ltp
from app.core.exit.broker_reconcile import reconcile_broker_positions

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])

# Smart suggestion refresh interval (seconds) — TA is expensive, don't run every tick
_SMART_SUGGESTION_INTERVAL = 60
# Broker reconciliation interval (seconds) — detect positions closed on Zerodha
_BROKER_RECONCILE_INTERVAL = 30


def _resolve_leg_qty(leg: Dict[str, Any], ticket_qty: int) -> int:
    raw = leg.get("qty", leg.get("quantity"))
    if raw is None:
        return max(1, int(ticket_qty))
    try:
        value = int(raw)
    except Exception:
        return max(1, int(ticket_qty))
    if value <= 0:
        return max(1, int(ticket_qty))
    if value <= 10 and ticket_qty > 1:
        return value * ticket_qty
    return value


def _try_get_mtm_with_ticker_cache(adapter: Any, intent: Any, is_zerodha: bool) -> float:
    """
    Get MTM using adapter, preferring live ticker cache for Zerodha positions.
    Falls back to REST API if ticker cache unavailable.
    """
    if not is_zerodha:
        # For paper, always use adapter MTM
        return adapter.mtm(intent)
    
    # For Zerodha, try to use live ticker cache for faster updates
    try:
        ticket = intent.ticket or {}
        # Compute correct quantity: prefer leg-level qty, fallback to ticket-level lots × lot_size
        ticket_qty = int(ticket.get("lot_size", 1)) * int(ticket.get("lots", 1))

        pnl_per_unit = 0.0
        all_cached = True
        
        for leg in ticket.get("legs", []):
            symbol = leg.get("symbol")
            if not symbol:
                all_cached = False
                break
            
            # Try ticker cache first
            current_price = get_ticker_ltp(symbol)
            if current_price is None:
                all_cached = False
                break
            
            entry_price = leg.get("price")
            if entry_price is None:
                all_cached = False
                break
            
            leg_qty = _resolve_leg_qty(leg, ticket_qty)
            sign = 1.0 if leg["side"] == "SELL" else -1.0
            pnl_per_unit += (float(entry_price) - float(current_price)) * sign * leg_qty
        
        if all_cached:
            # All prices available from ticker cache: use them
            logger.debug(f"📡 Using live ticker cache for {intent.intent_id}")
            return round(pnl_per_unit, 2)
    except Exception as e:
        logger.debug(f"⚠️  Ticker cache lookup failed for {intent.intent_id}: {e}")
    
    # Fallback to adapter MTM (REST API)
    return adapter.mtm(intent)


@router.websocket("/ws/positions")
async def ws_positions(websocket: WebSocket):
    await websocket.accept()
    logger.info("✅ WebSocket client connected for positions")

    # Initialize adapters
    paper_adapter = PaperExecutionAdapter()
    zerodha_adapter = None
    
    # Smart suggestion cache (refreshed every _SMART_SUGGESTION_INTERVAL seconds)
    _suggestion_cache: Dict[str, Any] = {}
    _suggestion_last_refresh: float = 0.0
    _broker_reconcile_last: float = 0.0
    
    try:
        kite = get_kite_client()
        zerodha_adapter = ZerodhaExecutionAdapter(kite_client=kite, dry_run=True)
        logger.info("✅ Zerodha adapter initialized")
    except Exception as e:
        logger.warning(f"⚠️  Zerodha adapter failed: {e}, will use paper adapter only")
        # Zerodha not configured, will use paper adapter as fallback
        pass

    try:
        while True:
            # Fetch latest open intents
            db = SessionLocal()
            try:
                intents = (
                    db.query(ExecutionIntent)
                    .order_by(ExecutionIntent.created_at.desc())
                    .limit(100)
                    .all()
                )
                
                logger.debug(f"📊 Fetched {len(intents)} intents from DB")

                updates: List[Dict[str, Any]] = []
                changed = False

                for intent in intents:
                    if intent is None:
                        continue

                    status = getattr(intent, "status", None)
                    closed_at = getattr(intent, "closed_at", None)
                    is_open = (status == "EXECUTED") and (closed_at is None)
                    if not is_open:
                        continue

                    # Support PAPER, ZERODHA_DRY_RUN, ZERODHA_LIVE, and ZERODHA_LIVE_DIRECT modes
                    mode = None
                    if isinstance(intent.execution_result, dict):
                        mode = intent.execution_result.get("mode")
                    
                    # Use appropriate adapter based on mode
                    is_zerodha_mode = mode and "ZERODHA" in str(mode).upper()
                    if is_zerodha_mode and zerodha_adapter:
                        adapter = zerodha_adapter
                    else:
                        adapter = paper_adapter

                    try:
                        # For Zerodha, prefer live ticker cache; fallback to REST API
                        mtm = _try_get_mtm_with_ticker_cache(adapter, intent, is_zerodha_mode)
                        setattr(intent, "pnl", mtm)
                        setattr(intent, "unrealized_pnl", mtm)
                        setattr(intent, "last_mtm_at", now_ist())
                        changed = True
                    except Exception as e:
                        logger.error(f"❌ Error calculating MTM for {intent.intent_id}: {e}")
                        # Continue with last known MTM instead of crashing
                        mtm = getattr(intent, "pnl", 0)

                    # Backfill margin for Zerodha modes if missing
                    try:
                        if is_zerodha_mode and zerodha_adapter:
                            mr = getattr(intent, "margin_required", None)
                            if (mr is None) or (float(mr or 0) <= 0):
                                computed_mr = zerodha_adapter.calculate_margin_required(intent)
                                if computed_mr and computed_mr > 0:
                                    setattr(intent, "margin_required", float(computed_mr))
                                    changed = True
                    except Exception as e:
                        logger.debug(f"⚠️  Margin computation failed for {intent.intent_id}: {e}")
                        # Non-blocking: margin computation failures should not break WS updates
                        pass

                    created_at = getattr(intent, "created_at", None)
                    ticket = getattr(intent, "ticket", {})
                    # Per-leg metrics (entry, LTP, P&L)
                    legs_metrics: List[Dict[str, Any]] = []
                    try:
                        # Only compute via Zerodha adapter (uses real LTP API)
                        if hasattr(adapter, "per_leg_metrics"):
                            legs_metrics = adapter.per_leg_metrics(intent)
                    except Exception as e:
                        logger.debug(f"⚠️  Per-leg metrics failed for {intent.intent_id}: {e}")
                        legs_metrics = []
                    
                    updates.append(
                        {
                            "intent_id": intent.intent_id,
                            "pnl": mtm,
                            "unrealized_pnl": mtm,
                            "entry_credit": intent.entry_credit,
                            "margin_required": getattr(intent, "margin_required", None),  # Margin blocked by broker
                            "status": intent.status,
                            "strategy": intent.strategy,
                            "underlying": intent.underlying,
                            "created_at": created_at.isoformat() if created_at is not None else None,
                            "tp": intent.tp,
                            "sl": intent.sl,
                            "ticket": ticket,  # Include full ticket with legs
                            "legs_metrics": legs_metrics,
                            "mode": mode,  # Include execution mode
                            "smart_suggestion": _suggestion_cache.get(intent.intent_id),
                        }
                    )

                if changed:
                    db.commit()

                # ── Broker reconciliation (detect positions closed on Zerodha) ──
                now_reconcile = time.time()
                if now_reconcile - _broker_reconcile_last >= _BROKER_RECONCILE_INTERVAL and zerodha_adapter:
                    try:
                        closed_ids = reconcile_broker_positions(db, force=True)
                        if closed_ids:
                            logger.info(f"🔄 WS reconcile: {len(closed_ids)} positions closed at broker")
                            # Remove closed positions from the update list
                            updates = [u for u in updates if u["intent_id"] not in closed_ids]
                    except Exception as e:
                        logger.debug(f"⚠️  Broker reconcile in WS loop failed: {e}")
                    _broker_reconcile_last = now_reconcile

                # ── Smart Suggestion refresh (throttled) ──────────
                now_ts = time.time()
                if now_ts - _suggestion_last_refresh >= _SMART_SUGGESTION_INTERVAL and updates:
                    try:
                        from app.core.position_advisor import advise_position
                        from app.core.spreads import detect_spreads

                        # A) App-originated positions with known strategy
                        for u in updates:
                            strat = u.get("strategy", "")
                            if strat in ("DIRECT_ZERODHA", "CUSTOM", ""):
                                continue
                            advice = advise_position(
                                strategy=strat,
                                underlying=u.get("underlying", ""),
                                db=db,
                                pnl=float(u.get("pnl", 0) or 0),
                                entry_credit=float(u.get("entry_credit", 0) or 0),
                            )
                            _suggestion_cache[u["intent_id"]] = advice
                            u["smart_suggestion"] = advice

                        # B) Zerodha-synced positions — detect spreads first
                        _SPREAD_TO_STRATEGY = {
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
                        zerodha_updates = [u for u in updates if u.get("strategy", "") in ("DIRECT_ZERODHA", "CUSTOM")]
                        if zerodha_updates:
                            # Build intent dicts for spread detector
                            z_dicts = []
                            for intent in intents:
                                if (intent.strategy or "") not in ("DIRECT_ZERODHA", "CUSTOM"):
                                    continue
                                z_dicts.append({
                                    "intent_id": intent.intent_id,
                                    "strategy": intent.strategy,
                                    "underlying": intent.underlying,
                                    "expiry": intent.expiry,
                                    "ticket": intent.ticket or {},
                                    "pnl": intent.pnl,
                                    "unrealized_pnl": intent.unrealized_pnl,
                                    "entry_credit": intent.entry_credit,
                                })
                            grouped = detect_spreads(z_dicts)
                            for spread in grouped.spreads:
                                strategy_name = _SPREAD_TO_STRATEGY.get(spread.spread_type, "")
                                underlying = spread.underlying or ""
                                if not strategy_name or not underlying:
                                    continue
                                combined_pnl = sum(float(leg.pnl or 0) for leg in spread.legs)
                                combined_credit = sum(float(leg.entry_credit or 0) for leg in spread.legs)
                                advice = advise_position(
                                    strategy=strategy_name,
                                    underlying=underlying,
                                    db=db,
                                    pnl=combined_pnl,
                                    entry_credit=combined_credit,
                                )
                                for leg in spread.legs:
                                    _suggestion_cache[leg.intent_id] = advice
                                # Also update the WS updates in-place
                                for u in zerodha_updates:
                                    if u["intent_id"] in _suggestion_cache:
                                        u["smart_suggestion"] = _suggestion_cache[u["intent_id"]]

                        _suggestion_last_refresh = now_ts
                        logger.info(f"🧠 Smart suggestions refreshed for {len(updates)} positions")
                    except Exception as e:
                        logger.warning(f"⚠️  Smart suggestion refresh failed: {e}")

                logger.debug(f"📤 Sending {len(updates)} position updates")

            finally:
                db.close()

            try:
                await websocket.send_json(
                    {
                        "type": "positions_update",
                        "ts": now_ist().isoformat(),
                        "intents": updates,
                    }
                )
            except Exception as e:
                logger.error(f"❌ Failed to send WebSocket message: {e}")
                raise

            # Push rate: keep it responsive but not too noisy
            await asyncio.sleep(1.0)

    except WebSocketDisconnect:
        logger.info("👋 WebSocket client disconnected")
        return
    except Exception as e:
        logger.error(f"❌ WebSocket error: {e}", exc_info=True)
        # If anything goes wrong, close gracefully.
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
