"""
Custom Watchlist API
Create, manage, and monitor symbol watchlists
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.db.session import SessionLocal
from app.db.models_watchlist import Watchlist, WatchlistAlert

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
            quote = kite.get_quote(symbol)
            if quote:
                quotes.append({
                    "symbol": symbol,
                    "ltp": quote.get("last_price"),
                    "change": quote.get("change"),
                    "change_pct": quote.get("change_percent"),
                    "volume": quote.get("volume"),
                    "high": quote.get("ohlc", {}).get("high"),
                    "low": quote.get("ohlc", {}).get("low"),
                    "open": quote.get("ohlc", {}).get("open"),
                    "close": quote.get("ohlc", {}).get("close"),
                })
        except Exception as e:
            # Fallback for symbols without quotes
            quotes.append({
                "symbol": symbol,
                "ltp": None,
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
