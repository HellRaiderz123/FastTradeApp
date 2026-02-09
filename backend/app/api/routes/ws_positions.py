from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.execution.paper import PaperExecutionAdapter
from app.core.execution.zerodha import ZerodhaExecutionAdapter
from app.core.broker.zerodha.client import get_kite_client
from app.core.utils.time import now_ist
from app.db.models_intent import ExecutionIntent
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/positions")
async def ws_positions(websocket: WebSocket):
    await websocket.accept()
    logger.info("✅ WebSocket client connected for positions")

    # Initialize adapters
    paper_adapter = PaperExecutionAdapter()
    zerodha_adapter = None
    
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

                    # Support both PAPER and ZERODHA_DRY_RUN modes
                    mode = None
                    if isinstance(intent.execution_result, dict):
                        mode = intent.execution_result.get("mode")
                    
                    # Skip only ZERODHA_LIVE mode for safety
                    if mode and str(mode).upper() == "ZERODHA_LIVE":
                        logger.debug(f"⏭️  Skipping ZERODHA_LIVE intent {intent.intent_id}")
                        continue

                    # Use appropriate adapter based on mode
                    if mode and "ZERODHA" in str(mode).upper() and zerodha_adapter:
                        adapter = zerodha_adapter
                    else:
                        adapter = paper_adapter

                    try:
                        mtm = adapter.mtm(intent)
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
                        if mode and "ZERODHA" in str(mode).upper() and zerodha_adapter:
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
                        }
                    )

                if changed:
                    db.commit()
                
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
