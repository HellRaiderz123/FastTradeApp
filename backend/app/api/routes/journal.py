import csv
import io
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

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
from app.core.risk.cost_calculator import estimate_round_trip_costs
from app.db.models_auto_trader import AutoTraderLog
from app.db.models_scanner_signal import ScannerSignalHistory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/journal", tags=["Journal"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _resolve_execution_mode(intent: Any) -> str:
    try:
        payload = getattr(intent, "execution_result_dict", None)
        if isinstance(payload, dict):
            mode = payload.get("mode")
            if mode:
                return str(mode)
    except Exception:
        pass

    payload = getattr(intent, "execution_result", None)
    if isinstance(payload, dict):
        return str(payload.get("mode") or "UNKNOWN")
    return "UNKNOWN"


def _build_tax_export_row(intent: Any) -> Dict[str, Any]:
    ticket = getattr(intent, "ticket_dict", None)
    if not isinstance(ticket, dict):
        raw_ticket = getattr(intent, "ticket", {})
        ticket = raw_ticket if isinstance(raw_ticket, dict) else {}

    ticket_qty = max(1, int(ticket.get("lot_size", 1) or 1) * int(ticket.get("lots", 1) or 1))
    legs_for_costs: List[Dict[str, Any]] = []
    for leg in ticket.get("legs", []):
        price = float(leg.get("price", 0.0) or 0.0)
        if price <= 0:
            continue
        leg_qty = int(leg.get("qty") or leg.get("quantity") or ticket_qty or 1)
        legs_for_costs.append({
            "side": str(leg.get("side", "BUY")).upper(),
            "price": price,
            "quantity": max(1, leg_qty),
        })

    estimated_charges = estimate_round_trip_costs(legs_for_costs) if legs_for_costs else 0.0
    gross_pnl = round(float(getattr(intent, "pnl", 0.0) or 0.0), 2)
    net_pnl = round(gross_pnl - estimated_charges, 2)
    entry_credit = round(float(getattr(intent, "entry_credit", 0.0) or 0.0), 2)

    created_at = getattr(intent, "created_at", None)
    closed_at = getattr(intent, "closed_at", None)
    holding_days = None
    if created_at and closed_at and hasattr(closed_at, "date") and hasattr(created_at, "date"):
        holding_days = max((closed_at.date() - created_at.date()).days, 0)

    return {
        "intent_id": getattr(intent, "intent_id", ""),
        "opened_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at or ""),
        "closed_at": closed_at.isoformat() if hasattr(closed_at, "isoformat") else str(closed_at or ""),
        "strategy": getattr(intent, "strategy", ""),
        "underlying": getattr(intent, "underlying", ""),
        "status": getattr(intent, "status", ""),
        "exit_reason": getattr(intent, "exit_reason", "") or "",
        "execution_mode": _resolve_execution_mode(intent),
        "entry_credit": entry_credit,
        "gross_pnl": gross_pnl,
        "estimated_charges": round(float(estimated_charges), 2),
        "net_pnl": net_pnl,
        "holding_days": holding_days,
    }


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
    intents = db.query(ExecutionIntent).order_by(ExecutionIntent.created_at.desc()).limit(limit).all()

    # Best-effort MTM refresh for open paper positions.
    # Batches all LTP lookups into a single call to avoid N+1 Zerodha API hits.
    try:
        from app.core.execution.paper import PaperExecutionAdapter
        from app.core.execution.base import get_ticket
        from app.core.market.ltp import get_ltp

        paper = PaperExecutionAdapter()
        open_paper_intents = []

        for intent in intents:
            if intent is None:
                continue
            if intent.status != "EXECUTED" or intent.closed_at is not None:
                continue
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
            open_paper_intents.append(intent)

        if open_paper_intents:
            # Collect ALL symbols across all open positions in one batch
            all_symbols = set()
            for intent in open_paper_intents:
                ticket = get_ticket(intent)
                for leg in ticket.get("legs", []):
                    sym = leg.get("symbol") or f'{leg.get("strike", "")}{leg.get("type", "")}'
                    if sym:
                        all_symbols.add(sym)

            # Single batched LTP call (1 Zerodha request instead of N)
            ltp_map = get_ltp(list(all_symbols)) if all_symbols else {}

            changed = False
            for intent in open_paper_intents:
                try:
                    ticket = get_ticket(intent)
                    ticket_qty = int(ticket.get("lot_size", 1)) * int(ticket.get("lots", 1))
                    pnl = 0.0
                    for leg in ticket.get("legs", []):
                        symbol = leg.get("symbol") or f'{leg.get("strike", "")}{leg.get("type", "")}'
                        current = ltp_map.get(symbol, 0.0)
                        entry = leg.get("price")
                        if entry is None:
                            continue
                        leg_qty = paper._resolve_leg_qty(leg, ticket_qty)
                        sign = 1.0 if leg["side"] == "SELL" else -1.0
                        pnl += (float(entry) - float(current)) * sign * leg_qty
                    intent.pnl = round(pnl, 2)
                    intent.unrealized_pnl = round(pnl, 2)
                    intent.last_mtm_at = now_ist()
                    changed = True
                except Exception:
                    pass

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


@router.get("/tax-export")
def tax_export(
    days: int = Query(365, ge=1, le=3650),
    format: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
):
    """Return closed-trade tax export rows with estimated charges and net P&L."""
    cutoff = now_ist() - timedelta(days=max(days - 1, 0))
    rows = (
        db.query(ExecutionIntent)
        .filter(ExecutionIntent.closed_at.isnot(None), ExecutionIntent.closed_at >= cutoff)
        .order_by(ExecutionIntent.closed_at.desc())
        .all()
    )

    payload_rows = [_build_tax_export_row(intent) for intent in rows]
    summary = {
        "trades": len(payload_rows),
        "gross_pnl": round(sum(float(row.get("gross_pnl") or 0.0) for row in payload_rows), 2),
        "estimated_charges": round(sum(float(row.get("estimated_charges") or 0.0) for row in payload_rows), 2),
        "net_pnl": round(sum(float(row.get("net_pnl") or 0.0) for row in payload_rows), 2),
    }

    if format.lower() == "csv":
        output = io.StringIO()
        fieldnames = [
            "intent_id", "opened_at", "closed_at", "strategy", "underlying",
            "status", "exit_reason", "execution_mode", "entry_credit",
            "gross_pnl", "estimated_charges", "net_pnl", "holding_days",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in payload_rows:
            writer.writerow(row)

        filename = f"fasttrade_tax_export_{now_ist().date().isoformat()}.csv"
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return {"rows": payload_rows, "summary": summary, "count": len(payload_rows), "days": days}


@router.get("/audit-trail")
def audit_trail(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(200, ge=10, le=1000),
    db: Session = Depends(get_db),
):
    """Unified audit trail across journal trades, scanner signals, and auto-trader actions."""
    cutoff = now_ist() - timedelta(days=max(days - 1, 0))
    rows: List[Dict[str, Any]] = []

    intents = (
        db.query(ExecutionIntent)
        .filter(ExecutionIntent.created_at >= cutoff)
        .order_by(ExecutionIntent.created_at.desc())
        .limit(limit)
        .all()
    )
    for intent in intents:
        rows.append({
            "timestamp": intent.closed_at or intent.created_at,
            "source": "JOURNAL",
            "event": intent.status,
            "symbol": intent.underlying,
            "strategy": intent.strategy,
            "intent_id": intent.intent_id,
            "details": {
                "pnl": intent.pnl,
                "entry_credit": intent.entry_credit,
                "mode": _resolve_execution_mode(intent),
                "exit_reason": intent.exit_reason,
            },
        })

    signals = (
        db.query(ScannerSignalHistory)
        .filter(ScannerSignalHistory.created_at >= cutoff)
        .order_by(ScannerSignalHistory.created_at.desc())
        .limit(limit)
        .all()
    )
    for signal in signals:
        rows.append({
            "timestamp": signal.executed_at or signal.last_seen_at or signal.created_at,
            "source": "SCANNER",
            "event": signal.status,
            "symbol": signal.symbol,
            "strategy": signal.strategy_name,
            "intent_id": signal.order_id,
            "details": signal.execution_payload_dict or signal.signal_payload_dict,
        })

    logs = (
        db.query(AutoTraderLog)
        .filter(AutoTraderLog.created_at >= cutoff)
        .order_by(AutoTraderLog.created_at.desc())
        .limit(limit)
        .all()
    )
    for log in logs:
        rows.append({
            "timestamp": log.created_at,
            "source": "AUTO_TRADER",
            "event": log.action,
            "symbol": log.underlying,
            "strategy": log.strategy,
            "intent_id": log.intent_id,
            "details": log.details,
        })

    rows.sort(key=lambda row: str(row.get("timestamp") or ""), reverse=True)
    return {"rows": rows[:limit], "count": min(len(rows), limit), "days": days}


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
    Disabled — Zerodha holdings/trades are no longer imported into FastTrade journal.
    Only trades executed from FastTrade app are tracked.
    """
    return {"success": True, "imported": 0, "holdings_synced": 0, "paired_trades": 0, "skipped": 0, "message": "Sync disabled — only FastTrade-executed trades are tracked"}
    try:
        kite = get_kite_client()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Zerodha not connected: {e}")

    try:
        orders = kite.orders() or []
        trades = kite.trades() or []
        holdings = kite.holdings() or []
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Zerodha API error: {e}")

    # Collect existing identifiers to skip duplicates
    existing_order_ids: set = set()
    existing_holding_symbols: set = set()
    for intent in db.query(ExecutionIntent).all():
        er = intent.execution_result_dict
        oid = er.get("order_id") or er.get("zerodha_order_id")
        if oid:
            existing_order_ids.add(str(oid))
        if er.get("source") == "zerodha_holding_sync":
            existing_holding_symbols.add(intent.underlying)

    added = 0
    skipped = 0

    # ── 1. HOLDINGS — long-term positions with unrealized P&L ─────────────────
    for h in holdings:
        symbol = (h.get("tradingsymbol") or "").strip()
        if not symbol:
            skipped += 1
            continue

        qty = int(h.get("quantity") or 0)
        avg_price = float(h.get("average_price") or 0)
        last_price = float(h.get("last_price") or 0)
        pnl = float(h.get("pnl") or 0)  # Zerodha gives unrealized P&L directly
        isin = h.get("isin", "")

        if qty == 0:
            skipped += 1
            continue

        # Update existing holding if already tracked
        existing = db.query(ExecutionIntent).filter(
            ExecutionIntent.underlying == symbol,
            ExecutionIntent.strategy == "ZERODHA_HOLDING",
            ExecutionIntent.closed_at.is_(None),
        ).first()

        if existing:
            # Refresh P&L and last price
            existing.pnl = round(pnl, 2)
            existing.unrealized_pnl = round(pnl, 2)
            er = existing.execution_result_dict
            er["last_price"] = last_price
            er["refreshed_at"] = now_ist().isoformat()
            existing.execution_result = er
            skipped += 1
            continue

        intent = ExecutionIntent(
            run_id=0,
            intent_id=f"zerodha_holding_{symbol}_{isin or now_ist().timestamp()}",
            strategy="ZERODHA_HOLDING",
            underlying=symbol,
            status="EXECUTED",
            executed=True,
            ticket={
                "legs": [{"symbol": symbol, "side": "BUY", "price": avg_price, "qty": qty}],
                "lot_size": 1, "lots": 1,
            },
            entry_credit=round(avg_price * qty, 2),
            pnl=round(pnl, 2),
            unrealized_pnl=round(pnl, 2),
            execution_result={
                "mode": "ZERODHA_HOLDING",
                "source": "zerodha_holding_sync",
                "isin": isin,
                "exchange": h.get("exchange", "NSE"),
                "product": h.get("product", "CNC"),
                "last_price": last_price,
                "synced_at": now_ist().isoformat(),
            },
            created_at=now_ist(),
            closed_at=None,   # open holding
            last_mtm_at=now_ist(),
        )
        try:
            db.add(intent)
            db.flush()
        except Exception:
            db.rollback()
            skipped += 1
            continue
        added += 1

    # ── 2. TODAY'S ORDERS — FIFO BUY+SELL pairing for realized P&L ─────────
    trade_fill: dict = {}
    for t in trades:
        oid = str(t.get("order_id", ""))
        if oid:
            trade_fill[oid] = float(t.get("average_price") or t.get("price") or 0)

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

    from collections import defaultdict
    symbol_buys: dict = defaultdict(list)
    completed_trades: list = []

    for order in complete_orders:
        order_id = str(order.get("order_id", ""))
        symbol = order.get("tradingsymbol", "").strip()
        txn = (order.get("transaction_type") or "BUY").upper()
        qty = int(order.get("filled_quantity") or order.get("quantity") or 0)
        price = trade_fill.get(order_id) or float(order.get("average_price") or order.get("price") or 0)
        ts = _ts(order)

        if txn == "BUY":
            symbol_buys[symbol].append({"price": price, "qty": qty, "order_id": order_id, "ts": ts, "order": order})
        elif txn == "SELL":
            remaining = qty
            buy_cost = sell_cost = 0.0
            matched_ids = []
            while remaining > 0 and symbol_buys[symbol]:
                buy = symbol_buys[symbol][0]
                mq = min(buy["qty"], remaining)
                buy_cost += buy["price"] * mq
                sell_cost += price * mq
                matched_ids.append(buy["order_id"])
                buy["qty"] -= mq
                remaining -= mq
                if buy["qty"] == 0:
                    symbol_buys[symbol].pop(0)
            matched_qty = qty - remaining
            if matched_qty > 0:
                completed_trades.append({
                    "symbol": symbol, "sell_order_id": order_id,
                    "buy_order_ids": matched_ids, "qty": matched_qty,
                    "buy_price": buy_cost / matched_qty,
                    "sell_price": price,
                    "pnl": sell_cost - buy_cost,
                    "ts": ts, "order": order,
                })

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
        try:
            db.add(intent)
            db.flush()
            existing_order_ids.add(sell_oid)
            added += 1
        except Exception:
            db.rollback()
            skipped += 1

    # Unmatched BUYs from today (no sell yet)
    for symbol, buys in symbol_buys.items():
        for buy in buys:
            oid = buy["order_id"]
            if oid in existing_order_ids:
                skipped += 1
                continue
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
                pnl=None, unrealized_pnl=None,
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
                closed_at=None,
                last_mtm_at=now_ist(),
            )
            try:
                db.add(intent)
                db.flush()
                existing_order_ids.add(oid)
                added += 1
            except Exception:
                db.rollback()
                skipped += 1

    if added:
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Zerodha sync commit failed: {e}")
            raise HTTPException(status_code=500, detail=f"DB commit failed: {e}")

    logger.info(f"✅ Zerodha sync: {added} added ({len(holdings)} holdings, {len(completed_trades)} paired trades), {skipped} skipped/refreshed")
    return {
        "success": True,
        "imported": added,
        "holdings_synced": len([h for h in holdings if h.get("quantity", 0) > 0]),
        "paired_trades": len(completed_trades),
        "skipped": skipped,
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
