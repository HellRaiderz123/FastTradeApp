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
    limit: int = Query(200, ge=1, le=1000),
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
    Pairs BUY+SELL orders per symbol to compute realized P&L.
    Skips duplicates matched by order_id in execution_result.
    """
    try:
        kite = get_kite_client()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Zerodha not connected: {e}")

    try:
        orders = kite.orders() or []
        trades = kite.trades() or []
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Zerodha API error: {e}")

    # Build order_id → fill price from trades (more accurate than order avg_price)
    trade_fill: dict = {}
    for t in trades:
        oid = str(t.get("order_id", ""))
        if oid:
            trade_fill[oid] = float(t.get("average_price") or t.get("price") or 0)

    # Collect existing order_ids to skip duplicates
    existing_order_ids: set = set()
    for intent in db.query(ExecutionIntent).all():
        er = intent.execution_result_dict
        oid = er.get("order_id") or er.get("zerodha_order_id")
        if oid:
            existing_order_ids.add(str(oid))

    # ── Build per-symbol FIFO queue to pair BUY→SELL and compute P&L ──────────
    # symbol → list of {price, qty, order_id, timestamp, transaction_type, order}
    from collections import defaultdict
    symbol_buys: dict = defaultdict(list)   # open buy lots waiting for a sell
    completed_trades: list = []             # fully paired trades with P&L
    unpaired_orders: list = []              # BUY orders with no matching SELL yet

    # Sort orders by timestamp so FIFO pairing is correct
    def _ts(o):
        ts = o.get("order_timestamp") or o.get("exchange_timestamp")
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                pass
        if isinstance(ts, datetime):
            return ts
        return datetime.min

    complete_orders = [
        o for o in orders
        if (o.get("status") or "").upper() == "COMPLETE"
        and o.get("tradingsymbol")
        and int(o.get("filled_quantity") or o.get("quantity") or 0) > 0
    ]
    complete_orders.sort(key=_ts)

    for order in complete_orders:
        order_id = str(order.get("order_id", ""))
        symbol = order.get("tradingsymbol", "").strip()
        txn = (order.get("transaction_type") or "BUY").upper()
        qty = int(order.get("filled_quantity") or order.get("quantity") or 0)
        price = trade_fill.get(order_id) or float(order.get("average_price") or order.get("price") or 0)
        ts = _ts(order)

        if txn == "BUY":
            symbol_buys[symbol].append({
                "price": price, "qty": qty,
                "order_id": order_id, "ts": ts, "order": order,
            })
        elif txn == "SELL":
            # FIFO match against open buys
            remaining_sell = qty
            sell_cost = 0.0
            buy_cost = 0.0
            matched_buy_ids = []

            while remaining_sell > 0 and symbol_buys[symbol]:
                buy = symbol_buys[symbol][0]
                matched_qty = min(buy["qty"], remaining_sell)
                buy_cost += buy["price"] * matched_qty
                sell_cost += price * matched_qty
                matched_buy_ids.append(buy["order_id"])

                buy["qty"] -= matched_qty
                remaining_sell -= matched_qty
                if buy["qty"] == 0:
                    symbol_buys[symbol].pop(0)

            realized_pnl = sell_cost - buy_cost
            matched_qty_total = qty - remaining_sell

            if matched_qty_total > 0:
                completed_trades.append({
                    "symbol": symbol,
                    "sell_order_id": order_id,
                    "buy_order_ids": matched_buy_ids,
                    "qty": matched_qty_total,
                    "buy_price": buy_cost / matched_qty_total if matched_qty_total else 0,
                    "sell_price": price,
                    "pnl": realized_pnl,
                    "ts": ts,
                    "order": order,
                })

    # Also add remaining unmatched BUY orders (open positions) as individual entries
    for symbol, buys in symbol_buys.items():
        for buy in buys:
            unpaired_orders.append(buy)

    added = 0
    skipped = 0

    # ── Insert completed (paired) trades ──────────────────────────────────────
    for trade in completed_trades:
        sell_oid = trade["sell_order_id"]
        if sell_oid in existing_order_ids:
            skipped += 1
            continue

        order = trade["order"]
        intent = ExecutionIntent(
            run_id=0,
            intent_id=f"zerodha_actual_{sell_oid}",
            strategy="ZERODHA_ACTUAL",
            underlying=trade["symbol"],
            status="EXECUTED",
            executed=True,
            ticket={
                "legs": [
                    {"symbol": trade["symbol"], "side": "BUY",  "price": round(trade["buy_price"], 2),  "qty": trade["qty"]},
                    {"symbol": trade["symbol"], "side": "SELL", "price": round(trade["sell_price"], 2), "qty": trade["qty"]},
                ],
                "lot_size": 1, "lots": 1,
            },
            entry_credit=round(trade["buy_price"] * trade["qty"], 2),
            pnl=round(trade["pnl"], 2),
            unrealized_pnl=0.0,
            execution_result={
                "mode": "ZERODHA_ACTUAL",
                "order_id": sell_oid,
                "buy_order_ids": trade["buy_order_ids"],
                "exchange": order.get("exchange", ""),
                "product": order.get("product", ""),
                "transaction_type": "SELL",
                "source": "zerodha_order_sync",
                "synced_at": now_ist().isoformat(),
            },
            created_at=trade["ts"],
            closed_at=trade["ts"],
            last_mtm_at=now_ist(),
            exit_reason="ZERODHA_ACTUAL",
        )
        db.add(intent)
        existing_order_ids.add(sell_oid)
        added += 1

    # ── Insert unmatched BUY orders as open positions ─────────────────────────
    for buy in unpaired_orders:
        oid = buy["order_id"]
        if oid in existing_order_ids:
            skipped += 1
            continue
        symbol = buy["order"].get("tradingsymbol", "").strip()
        order = buy["order"]
        intent = ExecutionIntent(
            run_id=0,
            intent_id=f"zerodha_actual_{oid}",
            strategy="ZERODHA_ACTUAL",
            underlying=symbol,
            status="EXECUTED",
            executed=True,
            ticket={
                "legs": [{"symbol": symbol, "side": "BUY", "price": buy["price"], "qty": buy["qty"]}],
                "lot_size": 1, "lots": 1,
            },
            entry_credit=round(buy["price"] * buy["qty"], 2),
            pnl=None,
            unrealized_pnl=None,
            execution_result={
                "mode": "ZERODHA_ACTUAL",
                "order_id": oid,
                "exchange": order.get("exchange", ""),
                "product": order.get("product", ""),
                "transaction_type": "BUY",
                "source": "zerodha_order_sync",
                "synced_at": now_ist().isoformat(),
            },
            created_at=buy["ts"],
            closed_at=None,   # still open
            last_mtm_at=now_ist(),
        )
        db.add(intent)
        existing_order_ids.add(oid)
        added += 1

    if added:
        db.commit()

    logger.info(f"✅ Zerodha sync: {added} trades imported ({len(completed_trades)} paired, {len(unpaired_orders)} open), {skipped} skipped")
    return {
        "success": True,
        "imported": added,
        "paired_trades": len(completed_trades),
        "open_positions": len(unpaired_orders),
        "skipped": skipped,
        "total_orders": len(orders),
    }


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
