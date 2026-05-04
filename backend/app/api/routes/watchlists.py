"""
Custom Watchlist API
Create, manage, and monitor symbol watchlists
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from collections import defaultdict

from app.db.session import SessionLocal
from app.db.models_watchlist import Watchlist, WatchlistAlert
from app.db.models_scanner_signal import ScannerSignalHistory

router = APIRouter(prefix="/watchlists", tags=["Watchlists"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class WatchlistCreate(BaseModel):
    name: str
    description: Optional[str] = None
    symbols: List[str] = []
    color: str = "#3b82f6"
    icon: Optional[str] = None
    is_default: bool = False


class WatchlistUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    symbols: Optional[List[str]] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    is_default: Optional[bool] = None


class SuggestionApplyRequest(BaseModel):
    symbols: List[str]


@router.get("")
def get_watchlists(include_inactive: bool = False, db: Session = Depends(get_db)):
    """Get all watchlists"""
    query = db.query(Watchlist)
    
    if not include_inactive:
        query = query.filter(Watchlist.is_active == True)
    
    watchlists = query.order_by(Watchlist.is_default.desc(), Watchlist.created_at.desc()).all()
    
    return {
        "watchlists": watchlists,
        "total": len(watchlists)
    }


@router.get("/{watchlist_id}")
def get_watchlist(watchlist_id: int, db: Session = Depends(get_db)):
    """Get a specific watchlist"""
    watchlist = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
    
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    
    return watchlist


@router.post("")
def create_watchlist(data: WatchlistCreate, db: Session = Depends(get_db)):
    """Create a new watchlist"""
    # Check for duplicate name
    existing = db.query(Watchlist).filter(Watchlist.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Watchlist with this name already exists")
    
    # If setting as default, unset other defaults
    if data.is_default:
        db.query(Watchlist).update({"is_default": False})
        db.commit()
    
    watchlist = Watchlist(
        name=data.name,
        description=data.description,
        symbols=data.symbols,
        color=data.color,
        icon=data.icon,
        is_default=data.is_default,
    )
    
    db.add(watchlist)
    db.commit()
    db.refresh(watchlist)
    
    return watchlist


@router.put("/{watchlist_id}")
def update_watchlist(watchlist_id: int, data: WatchlistUpdate, db: Session = Depends(get_db)):
    """Update a watchlist"""
    watchlist = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
    
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    
    # Update fields
    if data.name is not None:
        # Check for duplicate name
        existing = db.query(Watchlist).filter(
            Watchlist.name == data.name,
            Watchlist.id != watchlist_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Watchlist with this name already exists")
        watchlist.name = data.name
    
    if data.description is not None:
        watchlist.description = data.description
    
    if data.symbols is not None:
        watchlist.symbols = data.symbols
    
    if data.color is not None:
        watchlist.color = data.color
    
    if data.icon is not None:
        watchlist.icon = data.icon
    
    if data.is_default is not None:
        if data.is_default:
            # Unset other defaults
            db.query(Watchlist).filter(Watchlist.id != watchlist_id).update({"is_default": False})
        watchlist.is_default = data.is_default
    
    db.commit()
    db.refresh(watchlist)
    
    return watchlist


@router.delete("/{watchlist_id}")
def delete_watchlist(watchlist_id: int, soft_delete: bool = True, db: Session = Depends(get_db)):
    """Delete a watchlist"""
    watchlist = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
    
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    
    if soft_delete:
        # Soft delete (mark as inactive)
        watchlist.is_active = False
        db.commit()
        return {"message": "Watchlist deactivated", "id": watchlist_id}
    else:
        # Hard delete
        db.delete(watchlist)
        db.commit()
        return {"message": "Watchlist deleted", "id": watchlist_id}


@router.post("/{watchlist_id}/symbols/{symbol}")
def add_symbol(watchlist_id: int, symbol: str, db: Session = Depends(get_db)):
    """Add a symbol to watchlist"""
    watchlist = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
    
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    
    symbols = watchlist.symbols or []
    symbol_upper = symbol.upper()
    
    if symbol_upper not in symbols:
        symbols.append(symbol_upper)
        watchlist.symbols = symbols
        db.commit()
        db.refresh(watchlist)
    
    return watchlist


@router.delete("/{watchlist_id}/symbols/{symbol}")
def remove_symbol(watchlist_id: int, symbol: str, db: Session = Depends(get_db)):
    """Remove a symbol from watchlist"""
    watchlist = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
    
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    
    symbols = watchlist.symbols or []
    symbol_upper = symbol.upper()
    
    if symbol_upper in symbols:
        symbols.remove(symbol_upper)
        watchlist.symbols = symbols
        db.commit()
        db.refresh(watchlist)
    
    return watchlist


@router.get("/{watchlist_id}/quotes")
async def get_watchlist_quotes(watchlist_id: int, db: Session = Depends(get_db)):
    """Get live quotes for all symbols in watchlist"""
    watchlist = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
    
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    
    raw_symbols = watchlist.symbols or []
    if isinstance(raw_symbols, str):
        import json as _json
        try:
            raw_symbols = _json.loads(raw_symbols)
        except Exception:
            raw_symbols = []
    symbols = [s for s in raw_symbols if isinstance(s, str) and s.strip()]

    if not symbols:
        return {"watchlist": watchlist.name, "quotes": []}
    
    # Get quotes from market API
    from app.services.zerodha import KiteConnectService
    kite = KiteConnectService()
    
    quotes = []
    for symbol in symbols:
        try:
            full_quote = kite.get_full_quote(symbol) or {}
            ltp_quote = kite.get_quote(symbol) or {}
            quote = full_quote or ltp_quote

            if not quote:
                quotes.append({
                    "symbol": symbol,
                    "ltp": None,
                    "change": None,
                    "change_pct": None,
                    "change_percent": None,
                    "volume": None,
                    "high": None,
                    "low": None,
                    "open": None,
                    "close": None,
                    "error": "No quote data available",
                })
                continue

            ltp = quote.get("last_price")
            ohlc = quote.get("ohlc", {}) or {}
            prev_close = ohlc.get("close") or quote.get("close")

            change = quote.get("change")
            if change is None:
                change = quote.get("net_change")
            if change is None and ltp is not None and prev_close not in (None, 0):
                change = float(ltp) - float(prev_close)

            change_pct = quote.get("change_percent")
            if change_pct is None:
                change_pct = quote.get("change_pct")
            if change_pct is None and change is not None and prev_close not in (None, 0):
                change_pct = (float(change) / float(prev_close)) * 100

            quotes.append({
                "symbol": symbol,
                "ltp": round(float(ltp), 2) if ltp is not None else None,
                "change": round(float(change), 2) if change is not None else None,
                "change_pct": round(float(change_pct), 2) if change_pct is not None else None,
                "change_percent": round(float(change_pct), 2) if change_pct is not None else None,
                "volume": quote.get("volume"),
                "high": ohlc.get("high"),
                "low": ohlc.get("low"),
                "open": ohlc.get("open"),
                "close": prev_close,
            })
        except Exception as e:
            quotes.append({
                "symbol": symbol,
                "ltp": None,
                "change": None,
                "change_pct": None,
                "change_percent": None,
                "volume": None,
                "high": None,
                "low": None,
                "open": None,
                "close": None,
                "error": str(e)
            })
    
    return {
        "watchlist": {
            "id": watchlist.id,
            "name": watchlist.name,
            "color": watchlist.color,
        },
        "quotes": quotes
    }


@router.get("/{watchlist_id}/suggestions")
def get_watchlist_suggestions(
    watchlist_id: int,
    top_n: int = 10,
    days: int = 14,
    db: Session = Depends(get_db),
):
    """Generate ML-style watchlist suggestions from recent scanner signals."""
    watchlist = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    top_n = max(1, min(int(top_n), 30))
    days = max(3, min(int(days), 60))

    existing = {
        str(s).strip().upper()
        for s in (watchlist.symbols or [])
        if str(s).strip()
    }

    cutoff = datetime.utcnow().replace(tzinfo=None)
    from datetime import timedelta
    cutoff = cutoff - timedelta(days=days)

    rows = (
        db.query(ScannerSignalHistory)
        .filter(ScannerSignalHistory.first_seen_at >= cutoff)
        .order_by(ScannerSignalHistory.first_seen_at.desc())
        .limit(1200)
        .all()
    )

    by_symbol = defaultdict(lambda: {
        "count": 0,
        "bullish": 0,
        "bearish": 0,
        "latest_at": None,
        "latest_direction": None,
        "latest_strategy": None,
        "avg_change_pct": 0.0,
        "change_samples": 0,
        "strategies": set(),
    })

    for r in rows:
        sym = (r.symbol or "").strip().upper()
        if not sym or sym in existing:
            continue

        rec = by_symbol[sym]
        rec["count"] += 1
        direction = (r.direction or "").upper()
        if direction in {"LONG", "BUY", "BULLISH"}:
            rec["bullish"] += 1
        elif direction in {"SHORT", "SELL", "BEARISH"}:
            rec["bearish"] += 1

        if r.strategy_name:
            rec["strategies"].add(r.strategy_name)

        if rec["latest_at"] is None or (r.first_seen_at and r.first_seen_at > rec["latest_at"]):
            rec["latest_at"] = r.first_seen_at
            rec["latest_direction"] = r.direction
            rec["latest_strategy"] = r.strategy_name

        if r.change_percent is not None:
            rec["avg_change_pct"] += float(r.change_percent)
            rec["change_samples"] += 1

    suggestions = []
    for sym, rec in by_symbol.items():
        avg_change = (rec["avg_change_pct"] / rec["change_samples"]) if rec["change_samples"] else 0.0
        recency_bonus = 0
        if rec["latest_at"]:
            age_hrs = max(0.0, (datetime.utcnow().replace(tzinfo=None) - rec["latest_at"].replace(tzinfo=None)).total_seconds() / 3600.0)
            if age_hrs <= 24:
                recency_bonus = 3
            elif age_hrs <= 72:
                recency_bonus = 2
            elif age_hrs <= 120:
                recency_bonus = 1

        direction_bias = rec["bullish"] - rec["bearish"]
        score = (rec["count"] * 3) + recency_bonus + (direction_bias * 1.5)
        if abs(avg_change) >= 1.0:
            score += 1

        rationale = []
        rationale.append(f"{rec['count']} scanner signals in last {days} days")
        if rec["bullish"] > rec["bearish"]:
            rationale.append("Bullish directional bias")
        elif rec["bearish"] > rec["bullish"]:
            rationale.append("Bearish directional bias")
        if rec["latest_strategy"]:
            rationale.append(f"Latest strategy: {rec['latest_strategy']}")

        suggestions.append({
            "symbol": sym,
            "score": round(float(score), 2),
            "recent_signal_count": rec["count"],
            "bullish_count": rec["bullish"],
            "bearish_count": rec["bearish"],
            "latest_signal_at": rec["latest_at"].isoformat() if rec["latest_at"] else None,
            "latest_direction": rec["latest_direction"],
            "latest_strategy": rec["latest_strategy"],
            "avg_change_pct": round(avg_change, 2) if rec["change_samples"] else None,
            "rationale": rationale,
        })

    suggestions.sort(key=lambda x: (x["score"], x["recent_signal_count"]), reverse=True)
    suggestions = suggestions[:top_n]

    return {
        "watchlist": {
            "id": watchlist.id,
            "name": watchlist.name,
            "current_symbol_count": len(existing),
        },
        "window_days": days,
        "suggestions": suggestions,
    }


@router.post("/{watchlist_id}/apply-suggestions")
def apply_watchlist_suggestions(
    watchlist_id: int,
    payload: SuggestionApplyRequest,
    db: Session = Depends(get_db),
):
    """Apply one or more suggested symbols into a watchlist."""
    watchlist = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    symbols = [str(s).strip().upper() for s in (payload.symbols or []) if str(s).strip()]
    if not symbols:
        raise HTTPException(status_code=400, detail="No symbols provided")

    current = list(watchlist.symbols or [])
    existing = set(str(s).strip().upper() for s in current if str(s).strip())
    added = []
    skipped = []
    for sym in symbols:
        if sym in existing:
            skipped.append(sym)
            continue
        current.append(sym)
        existing.add(sym)
        added.append(sym)

    watchlist.symbols = sorted(existing)
    db.commit()
    db.refresh(watchlist)

    return {
        "success": True,
        "watchlist": {
            "id": watchlist.id,
            "name": watchlist.name,
            "symbol_count": len(watchlist.symbols or []),
        },
        "added": added,
        "skipped": skipped,
    }
