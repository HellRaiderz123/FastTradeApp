from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from datetime import datetime

from app.db.session import SessionLocal
from app.db.queries import get_recent_strategy_runs
from app.db.models_intent import ExecutionIntent
from app.api.schemas.journal import StrategyRunOut, ExecutionIntentOut
from app.core.utils.time import now_ist
from app.core.broker.zerodha.client import get_kite_client
from app.services.zerodha_ticker import subscribe_symbols as subscribe_to_ticker
from app.core.spreads import detect_spreads
from app.core.exit.broker_reconcile import reconcile_broker_positions
from app.core.learning.signal_diagnostics import compute_signal_diagnostics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/journal", tags=["Journal"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _sync_zerodha_live_positions(db: Session) -> List[ExecutionIntent]:
    """
    Fetch live positions from Zerodha and sync them to database if not already tracked.
    
    Returns:
        List of untracked Zerodha positions that were added/synced to the database.
    """
    synced = []
    try:
        kite = get_kite_client()
        zerodha_positions = kite.positions()
        net_positions = zerodha_positions.get("net", [])
        
        if not net_positions:
            return synced
        
        logger.info(f"🔄 Syncing {len(net_positions)} Zerodha positions to journal...")
        
        for zpos in net_positions:
            symbol = zpos.get("tradingsymbol", "").strip()
            quantity = zpos.get("quantity", 0)
            average_price = zpos.get("average_price", 0)
            last_price = zpos.get("last_price", 0)
            pnl = zpos.get("m2m", zpos.get("pnl", 0))
            
            if not symbol or quantity == 0:
                continue
            
            # Check if this position is already tracked in the database by symbol
            # Use a direct DB query for efficiency and to avoid race conditions
            already_tracked = db.query(ExecutionIntent).filter(
                ExecutionIntent.status == "EXECUTED",
                ExecutionIntent.closed_at.is_(None),
                ExecutionIntent.underlying == symbol,
                ExecutionIntent.strategy == "DIRECT_ZERODHA",
            ).first()
            
            if already_tracked:
                continue  # Already synced: skip
            
            # Also check if any other intent has this symbol in its legs
            existing = db.query(ExecutionIntent).filter(
                ExecutionIntent.status == "EXECUTED",
                ExecutionIntent.closed_at.is_(None)
            ).all()
            
            found = False
            for intent in existing:
                legs = intent.ticket_dict.get("legs", [])
                for leg in legs:
                    leg_symbol = leg.get("symbol", "")
                    if leg_symbol and leg_symbol == symbol:
                        found = True
                        break
                if found:
                    break
            
            # If not found in tracked intents, create a new entry for it
            if not found:
                logger.info(f"  ✅ Added untracked Zerodha position: {symbol}")
                
                intent = ExecutionIntent(
                    run_id=0,  # Not associated with a strategy run
                    intent_id=f"zerodha_live_{symbol}_{datetime.now().timestamp()}",
                    strategy="DIRECT_ZERODHA",
                    underlying=symbol,
                    status="EXECUTED",
                    executed=True,
                    ticket={
                        "legs": [{
                            "symbol": symbol,
                            "side": "BUY" if quantity > 0 else "SELL",
                            "price": average_price,
                            "qty": abs(quantity),
                        }],
                        "lot_size": 1,
                        "lots": 1,
                    },
                    entry_credit=average_price * abs(quantity),
                    pnl=pnl,
                    unrealized_pnl=pnl,
                    execution_result={
                        "mode": "ZERODHA_LIVE",
                        "created_at": now_ist().isoformat(),
                        "source": "zerodha_api_sync",
                    },
                    created_at=now_ist(),
                    last_mtm_at=now_ist(),
                )
                db.add(intent)
                synced.append(intent)
        
        if synced:
            db.commit()
            logger.info(f"  ✅ Synced {len(synced)} new Zerodha positions to journal")
            
            # Subscribe all synced position symbols to live ticker for MTM updates
            try:
                symbols = [zpos.get("tradingsymbol") for zpos in net_positions if zpos.get("tradingsymbol")]
                if symbols:
                    subscribe_to_ticker(symbols)
                    logger.info(f"  ✅ Subscribed {len(symbols)} symbols to live ticker")
            except Exception as e:
                logger.warning(f"⚠️  Failed to subscribe direct Zerodha positions to ticker: {e}")
    
    except Exception as e:
        logger.warning(f"⚠️  Failed to sync Zerodha positions: {e}")
        db.rollback()
    
    return synced


@router.get(
    "/strategy-runs",
    response_model=List[StrategyRunOut],
)
def list_strategy_runs(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return get_recent_strategy_runs(db, limit=limit)


@router.get(
    "/execution-intents",
    response_model=List[ExecutionIntentOut],
)
def list_execution_intents(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    List recent execution intents (active or closed trades).
    Includes both app-executed positions and direct Zerodha live positions.
    
    Returns:
        List of execution intents ordered by most recent first.
    """
    # Sync Zerodha live positions that aren't tracked in the app
    # AND reconcile stale positions that were closed on Zerodha directly
    try:
        _sync_zerodha_live_positions(db)
        reconcile_broker_positions(db, force=True)
    except Exception as e:
        logger.debug(f"⚠️  Zerodha position sync skipped: {e}")
        # Non-blocking: proceed with available data
    
    intents = db.query(ExecutionIntent).order_by(ExecutionIntent.created_at.desc()).limit(limit).all()

    # Best-effort MTM refresh for open paper positions.
    # (Uses Zerodha websocket ticks when available; REST fallback otherwise.)
    try:
        from app.core.execution.paper import PaperExecutionAdapter

        paper = PaperExecutionAdapter()
        changed = False
        for intent in intents:
            if intent is None:
                continue
            is_open = (intent.status == "EXECUTED") and (intent.closed_at is None)
            if not is_open:
                continue

            # Only compute MTM for paper intents (by convention stored in execution_result)
            mode = None
            if isinstance(intent.execution_result, dict):
                mode = intent.execution_result.get("mode")
            elif isinstance(intent.execution_result, str):
                import json as _json
                try:
                    mode = _json.loads(intent.execution_result).get("mode")
                except Exception:
                    pass
            if mode and str(mode).upper() != "PAPER":
                continue

            mtm = paper.mtm(intent)
            intent.pnl = mtm
            intent.unrealized_pnl = mtm
            intent.last_mtm_at = now_ist()
            changed = True

        if changed:
            db.commit()
    except Exception:
        # Never fail the list endpoint due to MTM calculation.
        pass

    return intents


@router.get("/spread-analysis")
def analyze_spreads(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Analyze open positions and group them into spreads.
    Detects incomplete spreads, naked positions, and associated risks.
    
    Returns:
        {
            "spreads": [ { spread analysis } ],
            "naked_positions": [ { naked position details } ],
            "incomplete_spreads": [ { incomplete spread with warning } ],
            "total_warnings": [ { warning details } ],
            "has_critical_warnings": boolean
        }
    """
    # Get active execution intents
    intents = (
        db.query(ExecutionIntent)
        .filter(ExecutionIntent.status == "EXECUTED", ExecutionIntent.closed_at.is_(None))
        .order_by(ExecutionIntent.created_at.desc())
        .limit(limit)
        .all()
    )
    
    def _parse_json(value):
        """Coerce JSON column to dict — handles string values from PostgreSQL."""
        if isinstance(value, str):
            import json as _json
            try:
                return _json.loads(value)
            except Exception:
                return {}
        return value if isinstance(value, dict) else {}

    # Convert to dicts for the detector
    intent_dicts = [
        {
            "intent_id": intent.intent_id,
            "strategy": intent.strategy,
            "underlying": intent.underlying,
            "expiry": intent.expiry,
            "ticket": intent.ticket_dict,
            "pnl": intent.pnl,
            "unrealized_pnl": intent.unrealized_pnl,
            "entry_credit": intent.entry_credit,
        }
        for intent in intents
    ]

    # Debug log ticket structures for troubleshooting
    for d in intent_dicts:
        ticket = d.get("ticket", {})
        legs = ticket.get("legs", [])
        logger.debug(
            "Spread analysis intent=%s strategy=%s underlying=%s legs=%s",
            d.get("intent_id"), d.get("strategy"), d.get("underlying"),
            [{k: v for k, v in leg.items() if k in ("side", "type", "option_type", "strike", "symbol", "qty", "quantity")} for leg in legs],
        )
    
    # Run spread detection
    grouped = detect_spreads(intent_dicts)
    
    return grouped.to_dict()


@router.get("/signal-diagnostics")
def signal_diagnostics(
    limit: int = Query(200, ge=10, le=1000),
    lookback_days: int = Query(30, ge=1, le=365),
    underlying: Optional[str] = Query(None),
    strategy: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Rule-based diagnostics for closed trades based on signal snapshots.

    Returns aggregated stats to explain loss drivers and weak signal regimes.
    """
    return compute_signal_diagnostics(
        db,
        limit=limit,
        lookback_days=lookback_days,
        underlying=underlying,
        strategy=strategy,
    )


@router.delete("/execution-intents/closed")
def delete_closed_trades(
    db: Session = Depends(get_db),
):
    """
    Bulk-delete all closed (completed) execution intents from the journal.
    Open positions (closed_at IS NULL) are preserved.
    """
    closed = db.query(ExecutionIntent).filter(ExecutionIntent.closed_at.isnot(None)).all()
    count = len(closed)
    for intent in closed:
        db.delete(intent)
    db.commit()
    logger.info(f"🗑️ Bulk-deleted {count} closed trades from journal")
    return {"success": True, "deleted": count}


@router.post("/sync-zerodha")
def sync_zerodha_trades(
    db: Session = Depends(get_db),
):
    """
    Import actual executed trades from Zerodha orders/trades API.
    Creates ZERODHA_ACTUAL journal entries for trades not already tracked.
    Skips duplicates (matched by order_id stored in execution_result).
    """
    import json as _json

    try:
        kite = get_kite_client()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Zerodha not connected: {e}")

    # Fetch orders and trades from Zerodha
    try:
        orders = kite.orders() or []
        trades = kite.trades() or []
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Zerodha API error: {e}")

    # Build a map of order_id → trade fill details
    trade_map: dict = {}
    for t in trades:
        oid = str(t.get("order_id", ""))
        if oid:
            trade_map[oid] = t

    # Collect all existing order_ids already in DB to avoid duplicates
    existing_intents = db.query(ExecutionIntent).all()
    existing_order_ids: set = set()
    for intent in existing_intents:
        er = intent.execution_result_dict
        oid = er.get("order_id") or er.get("zerodha_order_id")
        if oid:
            existing_order_ids.add(str(oid))

    added = 0
    skipped = 0

    for order in orders:
        order_id = str(order.get("order_id", ""))
        status = (order.get("status") or "").upper()

        # Only import COMPLETE orders
        if status != "COMPLETE":
            skipped += 1
            continue

        if order_id in existing_order_ids:
            skipped += 1
            continue

        symbol = order.get("tradingsymbol", "").strip()
        transaction_type = order.get("transaction_type", "BUY").upper()
        qty = int(order.get("filled_quantity") or order.get("quantity") or 0)
        avg_price = float(order.get("average_price") or order.get("price") or 0)
        order_timestamp = order.get("order_timestamp") or order.get("exchange_timestamp")

        if not symbol or qty == 0:
            skipped += 1
            continue

        # Get fill price from trades if available
        fill = trade_map.get(order_id, {})
        fill_price = float(fill.get("average_price") or avg_price)

        # Determine if this is a closing trade (SELL for equity)
        # For simplicity, treat each order as its own journal entry
        entry_value = fill_price * qty

        # Parse order timestamp
        created = now_ist()
        if order_timestamp:
            try:
                if isinstance(order_timestamp, str):
                    created = datetime.fromisoformat(order_timestamp.replace("Z", "+00:00"))
                else:
                    created = order_timestamp
            except Exception:
                pass

        intent = ExecutionIntent(
            run_id=0,
            intent_id=f"zerodha_actual_{order_id}",
            strategy="ZERODHA_ACTUAL",
            underlying=symbol,
            status="EXECUTED",
            executed=True,
            ticket={
                "legs": [{
                    "symbol": symbol,
                    "side": transaction_type,
                    "price": fill_price,
                    "qty": qty,
                }],
                "lot_size": 1,
                "lots": 1,
            },
            entry_credit=entry_value,
            pnl=0.0,
            unrealized_pnl=0.0,
            execution_result={
                "mode": "ZERODHA_ACTUAL",
                "order_id": order_id,
                "exchange": order.get("exchange", ""),
                "product": order.get("product", ""),
                "order_type": order.get("order_type", ""),
                "transaction_type": transaction_type,
                "source": "zerodha_order_sync",
                "synced_at": now_ist().isoformat(),
            },
            created_at=created,
            last_mtm_at=now_ist(),
            # Mark as closed since it's a completed historical order
            closed_at=created,
            exit_reason="ZERODHA_ACTUAL",
        )
        db.add(intent)
        existing_order_ids.add(order_id)
        added += 1

    if added:
        db.commit()

    logger.info(f"✅ Zerodha sync: {added} new trades imported, {skipped} skipped")
    return {"success": True, "imported": added, "skipped": skipped, "total_orders": len(orders)}


@router.delete("/execution-intents/{intent_id}")
def delete_execution_intent(
    intent_id: str,
    db: Session = Depends(get_db),
):
    """
    Delete an execution intent from the journal.
    This permanently removes the trade record from the database.
    """
    intent = db.query(ExecutionIntent).filter(ExecutionIntent.intent_id == intent_id).first()
    
    if not intent:
        raise HTTPException(status_code=404, detail="Execution intent not found")
    
    # Store info for response before deletion
    deleted_info = {
        "intent_id": intent.intent_id,
        "strategy": intent.strategy,
        "underlying": intent.underlying,
        "deleted_at": now_ist().isoformat(),
    }
    
    db.delete(intent)
    db.commit()
    
    logger.info(f"🗑️ Deleted execution intent: {intent_id} ({intent.strategy} - {intent.underlying})")
    
    return {
        "success": True,
        "message": "Execution intent deleted successfully",
        **deleted_info,
    }
