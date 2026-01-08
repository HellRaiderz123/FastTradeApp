from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.execution.paper import PaperExecutionAdapter
from app.core.execution.zerodha import ZerodhaExecutionAdapter
from app.core.broker.zerodha.client import get_kite_client
from app.core.utils.time import now_ist
from app.db.models_intent import ExecutionIntent
from app.db.session import SessionLocal

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/positions")
async def ws_positions(websocket: WebSocket):
    await websocket.accept()

    # Initialize adapters
    paper_adapter = PaperExecutionAdapter()
    zerodha_adapter = None
    
    try:
        kite = get_kite_client()
        zerodha_adapter = ZerodhaExecutionAdapter(kite_client=kite, dry_run=True)
    except:
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
                        continue

                    # Use appropriate adapter based on mode
                    if mode and "ZERODHA" in str(mode).upper() and zerodha_adapter:
                        adapter = zerodha_adapter
                    else:
                        adapter = paper_adapter

                    mtm = adapter.mtm(intent)
                    setattr(intent, "pnl", mtm)
                    setattr(intent, "unrealized_pnl", mtm)
                    setattr(intent, "last_mtm_at", now_ist())
                    changed = True

                    # Backfill margin for Zerodha modes if missing
                    try:
                        if mode and "ZERODHA" in str(mode).upper() and zerodha_adapter:
                            mr = getattr(intent, "margin_required", None)
                            if (mr is None) or (float(mr or 0) <= 0):
                                computed_mr = zerodha_adapter.calculate_margin_required(intent)
                                if computed_mr and computed_mr > 0:
                                    setattr(intent, "margin_required", float(computed_mr))
                                    changed = True
                    except Exception:
                        # Non-blocking: margin computation failures should not break WS updates
                        pass

                    created_at = getattr(intent, "created_at", None)
                    ticket = getattr(intent, "ticket", {})
                    # Per-leg metrics (entry, LTP, P&L)
                    legs_metrics: List[Dict[str, Any]] = []
                    try:
                        # Only compute via Zerodha adapter (uses real LTP API)
                        legs_metrics = adapter.per_leg_metrics(intent) if hasattr(adapter, "per_leg_metrics") else []
                    except Exception:
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

            finally:
                db.close()

            await websocket.send_json(
                {
                    "type": "positions_update",
                    "ts": now_ist().isoformat(),
                    "intents": updates,
                }
            )

            # Push rate: keep it responsive but not too noisy
            await asyncio.sleep(1.0)

    except WebSocketDisconnect:
        return
    except Exception:
        # If anything goes wrong, close gracefully.
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
