"""
holdings.py
-----------
REST API for stock/cash holdings created via AI Chat or Strategy Scanner.
Tracks paper and live equity positions separately from options intents.

Endpoints:
  GET    /holdings              — list open (or all) holdings
  POST   /holdings              — manually create a holding
  GET    /holdings/{id}         — get one holding
  PATCH  /holdings/{id}/price   — update current price & recalc P&L
  POST   /holdings/{id}/close   — close a holding
  POST   /holdings/close-all    — close ALL open holdings
  DELETE /holdings/{id}         — hard delete a holding record
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.utils.time import now_ist
from app.db.models_stock_holding import StockHolding
from app.db.session import SessionLocal
from app.services.zerodha import KiteConnectService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/holdings", tags=["holdings"])

kite_service = KiteConnectService()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Pydantic schemas ────────────────────────────────────────────────────────

class HoldingCreate(BaseModel):
    symbol: str
    direction: str = "BUY"
    quantity: int
    entry_price: float
    strategy_name: Optional[str] = None
    source: str = "SCANNER"
    execution_mode: Optional[str] = "PAPER"
    order_id: Optional[str] = None
    tp_pct: Optional[float] = None
    sl_pct: Optional[float] = None
    tsl_pct: Optional[float] = None


class HoldingCloseBody(BaseModel):
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = "MANUAL"


# ── Helpers ─────────────────────────────────────────────────────────────────

def _get_ltp(symbol: str) -> Optional[float]:
    try:
        quote = kite_service.get_quote(symbol)
        if quote:
            return float(quote.get("last_price") or 0) or None
    except Exception:
        pass
    return None


def _recalc_pnl(holding: StockHolding) -> float:
    price = holding.current_price or holding.entry_price
    if holding.direction == "BUY":
        return round((price - holding.entry_price) * holding.quantity, 2)
    return round((holding.entry_price - price) * holding.quantity, 2)


def _enrich_with_ltp(holdings: List[StockHolding]) -> List[dict]:
    """Fetch live LTP for all open holdings and update P&L."""
    symbols = list({h.symbol for h in holdings if h.status == "OPEN"})
    ltps: dict = {}
    if symbols:
        try:
            quotes = kite_service.get_bulk_quotes(symbols) or {}
            for sym in symbols:
                q = quotes.get(f"NSE:{sym}") or quotes.get(sym)
                if q:
                    ltps[sym] = float(q.get("last_price") or 0)
        except Exception:
            pass

    result = []
    for h in holdings:
        d = h.to_dict()
        if h.status == "OPEN" and h.symbol in ltps and ltps[h.symbol] > 0:
            ltp = ltps[h.symbol]
            d["current_price"] = ltp
            if h.direction == "BUY":
                d["pnl"] = round((ltp - h.entry_price) * h.quantity, 2)
            else:
                d["pnl"] = round((h.entry_price - ltp) * h.quantity, 2)
            d["current_value"] = round(ltp * h.quantity, 2)
        result.append(d)
    return result


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("")
def list_holdings(
    status: Optional[str] = Query(None, description="OPEN | CLOSED | all"),
    source: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    q = db.query(StockHolding).order_by(StockHolding.created_at.desc())
    if status and status.upper() != "ALL":
        q = q.filter(StockHolding.status == status.upper())
    else:
        # default: show only OPEN
        if not status:
            q = q.filter(StockHolding.status == "OPEN")
    if source:
        q = q.filter(StockHolding.source == source.upper())
    if symbol:
        q = q.filter(StockHolding.symbol == symbol.upper())

    holdings = q.limit(limit).all()
    enriched = _enrich_with_ltp(holdings)

    total_pnl = sum(h.get("pnl", 0) or 0 for h in enriched)
    total_invested = sum(h.get("invested_value", 0) or 0 for h in enriched)
    return {
        "holdings": enriched,
        "count": len(enriched),
        "total_pnl": round(total_pnl, 2),
        "total_invested": round(total_invested, 2),
    }


@router.post("")
def create_holding(body: HoldingCreate, db: Session = Depends(get_db)):
    holding = StockHolding(
        symbol=body.symbol.upper().strip(),
        direction=body.direction.upper(),
        quantity=body.quantity,
        entry_price=body.entry_price,
        current_price=body.entry_price,
        strategy_name=body.strategy_name,
        source=body.source.upper(),
        execution_mode=body.execution_mode,
        order_id=body.order_id,
        tp_pct=body.tp_pct,
        sl_pct=body.sl_pct,
        tsl_pct=body.tsl_pct,
        status="OPEN",
        pnl=0.0,
    )
    db.add(holding)
    db.commit()
    db.refresh(holding)
    return {"holding": holding.to_dict(), "message": f"Holding created for {holding.symbol}"}


@router.get("/{holding_id}")
def get_holding(holding_id: int, db: Session = Depends(get_db)):
    h = db.query(StockHolding).filter(StockHolding.id == holding_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="Holding not found")
    enriched = _enrich_with_ltp([h])
    return enriched[0]


@router.patch("/{holding_id}/price")
def update_price(holding_id: int, db: Session = Depends(get_db)):
    """Refresh current price from Zerodha and recalculate P&L."""
    h = db.query(StockHolding).filter(StockHolding.id == holding_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="Holding not found")
    ltp = _get_ltp(h.symbol)
    if ltp:
        h.current_price = ltp
        h.pnl = _recalc_pnl(h)
        db.commit()
    return h.to_dict()


@router.post("/{holding_id}/close")
def close_holding(holding_id: int, body: HoldingCloseBody = HoldingCloseBody(), db: Session = Depends(get_db)):
    h = db.query(StockHolding).filter(StockHolding.id == holding_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="Holding not found")
    if h.status == "CLOSED":
        return {"message": "Already closed", "holding": h.to_dict()}

    exit_price = body.exit_price or _get_ltp(h.symbol) or h.current_price or h.entry_price
    if h.direction == "BUY":
        final_pnl = round((exit_price - h.entry_price) * h.quantity, 2)
    else:
        final_pnl = round((h.entry_price - exit_price) * h.quantity, 2)

    h.status = "CLOSED"
    h.exit_price = exit_price
    h.exit_reason = body.exit_reason or "MANUAL"
    h.closed_at = now_ist()
    h.pnl = final_pnl
    h.current_price = exit_price
    db.commit()
    return {"message": f"Closed {h.symbol} @ ₹{exit_price}", "pnl": final_pnl, "holding": h.to_dict()}


@router.post("/close-all")
def close_all_holdings(db: Session = Depends(get_db)):
    """Close ALL open holdings at current market price."""
    open_holdings = db.query(StockHolding).filter(StockHolding.status == "OPEN").all()
    if not open_holdings:
        return {"message": "No open holdings to close", "closed": 0, "total_pnl": 0}

    # Fetch LTPs in bulk
    symbols = list({h.symbol for h in open_holdings})
    ltps: dict = {}
    try:
        quotes = kite_service.get_bulk_quotes(symbols) or {}
        for sym in symbols:
            q = quotes.get(f"NSE:{sym}") or quotes.get(sym)
            if q:
                ltps[sym] = float(q.get("last_price") or 0)
    except Exception:
        pass

    total_pnl = 0.0
    closed_count = 0
    now = now_ist()

    for h in open_holdings:
        exit_price = ltps.get(h.symbol) or h.current_price or h.entry_price
        if h.direction == "BUY":
            pnl = round((exit_price - h.entry_price) * h.quantity, 2)
        else:
            pnl = round((h.entry_price - exit_price) * h.quantity, 2)

        h.status = "CLOSED"
        h.exit_price = exit_price
        h.exit_reason = "CLOSE_ALL"
        h.closed_at = now
        h.pnl = pnl
        h.current_price = exit_price
        total_pnl += pnl
        closed_count += 1

    db.commit()
    return {
        "message": f"Closed {closed_count} holding(s)",
        "closed": closed_count,
        "total_pnl": round(total_pnl, 2),
    }


@router.delete("/{holding_id}")
def delete_holding(holding_id: int, db: Session = Depends(get_db)):
    h = db.query(StockHolding).filter(StockHolding.id == holding_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="Holding not found")
    db.delete(h)
    db.commit()
    return {"message": f"Deleted holding {holding_id}"}


# ── Helper used by scanner + AI chat ────────────────────────────────────────

def create_stock_holding(
    db: Session,
    *,
    symbol: str,
    direction: str,
    quantity: int,
    entry_price: float,
    strategy_name: Optional[str] = None,
    source: str = "SCANNER",
    execution_mode: Optional[str] = "PAPER",
    order_id: Optional[str] = None,
    tp_pct: Optional[float] = None,
    sl_pct: Optional[float] = None,
    tsl_pct: Optional[float] = None,
) -> StockHolding:
    """Create a StockHolding record. Caller must commit."""
    holding = StockHolding(
        symbol=symbol.upper().strip(),
        direction=direction.upper(),
        quantity=quantity,
        entry_price=entry_price,
        current_price=entry_price,
        strategy_name=strategy_name,
        source=source.upper(),
        execution_mode=execution_mode,
        order_id=order_id,
        tp_pct=tp_pct,
        sl_pct=sl_pct,
        tsl_pct=tsl_pct,
        status="OPEN",
        pnl=0.0,
    )
    db.add(holding)
    return holding


def has_open_holding(db: Session, symbol: str) -> bool:
    """Return True if there is already an open holding for this symbol."""
    return db.query(StockHolding).filter(
        StockHolding.symbol == symbol.upper().strip(),
        StockHolding.status == "OPEN",
    ).first() is not None
