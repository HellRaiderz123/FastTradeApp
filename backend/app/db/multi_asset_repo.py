"""
multi_asset_repo.py
-------------------
Repository for multi-asset models: Symbol, MarketData, AlertRule.

Provides CRUD operations for NIFTY 50 stocks, market data, and alert rules.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
import logging

from app.db.models import Symbol, MarketData, AlertRule
from app.core.utils.time import now_ist

logger = logging.getLogger(__name__)


# ===================================================================
# SYMBOL REPOSITORY
# ===================================================================

def create_symbol(
    db: Session,
    ticker: str,
    name: str,
    asset_type: str = "STOCK",
    sector: Optional[str] = None,
    is_nifty50: bool = False,
    **kwargs
) -> Symbol:
    """Create a new symbol record"""
    symbol = Symbol(
        ticker=ticker,
        name=name,
        asset_type=asset_type,
        sector=sector,
        is_nifty50=is_nifty50,
        **kwargs
    )
    db.add(symbol)
    db.commit()
    db.refresh(symbol)
    logger.info(f"✅ Symbol created: {ticker}")
    return symbol


def get_symbol(db: Session, ticker: str) -> Optional[Symbol]:
    """Get symbol by ticker"""
    return db.query(Symbol).filter_by(ticker=ticker).first()


def get_symbol_by_id(db: Session, symbol_id: int) -> Optional[Symbol]:
    """Get symbol by ID"""
    return db.query(Symbol).filter_by(id=symbol_id).first()


def list_nifty50(db: Session, active_only: bool = True) -> List[Symbol]:
    """List all NIFTY 50 stocks"""
    query = db.query(Symbol).filter_by(is_nifty50=True)
    if active_only:
        query = query.filter_by(is_active=True)
    return query.order_by(asc(Symbol.nifty_50_rank)).all()


def list_symbols_by_sector(db: Session, sector: str) -> List[Symbol]:
    """List all stocks in a sector"""
    return db.query(Symbol).filter_by(sector=sector, is_active=True).all()


def search_symbols(db: Session, search_term: str) -> List[Symbol]:
    """Search symbols by ticker or name"""
    search = f"%{search_term.upper()}%"
    return db.query(Symbol).filter(
        or_(
            Symbol.ticker.like(search),
            Symbol.name.like(search)
        )
    ).filter_by(is_active=True).all()


def update_symbol_fundamentals(
    db: Session,
    symbol_id: int,
    fundamentals: Dict[str, Any]
) -> Symbol:
    """Update fundamental data for a symbol"""
    symbol = db.query(Symbol).filter_by(id=symbol_id).first()
    if not symbol:
        raise ValueError(f"Symbol ID {symbol_id} not found")
    
    for key, value in fundamentals.items():
        if hasattr(symbol, key):
            setattr(symbol, key, value)
    
    symbol.last_fundamental_update = now_ist()
    db.commit()
    db.refresh(symbol)
    logger.info(f"✅ Fundamentals updated: {symbol.ticker}")
    return symbol


# ===================================================================
# MARKET DATA REPOSITORY
# ===================================================================

def create_market_data(
    db: Session,
    symbol_id: int,
    ticker: str,
    timeframe: str,
    timestamp: datetime,
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float,
    open_interest: Optional[float] = None,
    is_complete: bool = False,
    source: str = "zerodha"
) -> MarketData:
    """Create market data candle"""
    candle = MarketData(
        symbol_id=symbol_id,
        ticker=ticker,
        timeframe=timeframe,
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        open_interest=open_interest,
        is_complete=is_complete,
        source=source,
    )
    db.add(candle)
    db.commit()
    db.refresh(candle)
    return candle


def get_candles(
    db: Session,
    ticker: str,
    timeframe: str,
    count: int = 100,
    end_time: Optional[datetime] = None
) -> List[MarketData]:
    """Get last N candles for a symbol"""
    query = db.query(MarketData).filter_by(
        ticker=ticker,
        timeframe=timeframe
    )
    
    if end_time:
        query = query.filter(MarketData.timestamp <= end_time)
    
    return query.order_by(desc(MarketData.timestamp)).limit(count).all()[::-1]


def get_candle_range(
    db: Session,
    ticker: str,
    timeframe: str,
    start_time: datetime,
    end_time: datetime
) -> List[MarketData]:
    """Get candles within time range"""
    return db.query(MarketData).filter(
        and_(
            MarketData.ticker == ticker,
            MarketData.timeframe == timeframe,
            MarketData.timestamp >= start_time,
            MarketData.timestamp <= end_time
        )
    ).order_by(asc(MarketData.timestamp)).all()


def get_latest_candle(
    db: Session,
    ticker: str,
    timeframe: str
) -> Optional[MarketData]:
    """Get latest candle for a symbol"""
    return db.query(MarketData).filter_by(
        ticker=ticker,
        timeframe=timeframe
    ).order_by(desc(MarketData.timestamp)).first()


def update_candle(
    db: Session,
    candle_id: int,
    **updates
) -> MarketData:
    """Update candle data (for incomplete candles)"""
    candle = db.query(MarketData).filter_by(id=candle_id).first()
    if not candle:
        raise ValueError(f"Candle ID {candle_id} not found")
    
    for key, value in updates.items():
        if hasattr(candle, key):
            setattr(candle, key, value)
    
    db.commit()
    db.refresh(candle)
    return candle


def delete_old_candles(
    db: Session,
    days_to_keep: int = 365
) -> int:
    """Delete candles older than specified days (for archival)"""
    cutoff = datetime.utcnow() - timedelta(days=days_to_keep)
    count = db.query(MarketData).filter(
        MarketData.created_at < cutoff
    ).delete()
    db.commit()
    logger.info(f"🗑️ Deleted {count} old candles (older than {days_to_keep} days)")
    return count


# ===================================================================
# ALERT RULE REPOSITORY
# ===================================================================

def create_alert_rule(
    db: Session,
    name: str,
    ticker: str,
    alert_type: str,
    condition: Dict[str, Any],
    is_enabled: bool = True,
    notify_via: Optional[Dict] = None,
    action_on_trigger: Optional[str] = None,
    created_by: Optional[str] = None
) -> AlertRule:
    """Create new alert rule"""
    symbol = get_symbol(db, ticker)
    if not symbol:
        # Auto-create symbol if it doesn't exist
        logger.info(f"Auto-creating symbol: {ticker}")
        symbol = create_symbol(
            db=db,
            ticker=ticker,
            name=ticker,  # Use ticker as name for now
            asset_type="STOCK",
            is_active=True
        )
    
    rule = AlertRule(
        name=name,
        symbol_id=symbol.id,
        ticker=ticker,
        alert_type=alert_type,
        condition=condition,
        is_enabled=is_enabled,
        notify_via=notify_via or {"email": True, "push": True},
        action_on_trigger=action_on_trigger,
        created_by=created_by,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    logger.info(f"✅ Alert rule created: {name} for {ticker}")
    return rule


def get_alert_rule(db: Session, rule_id: int) -> Optional[AlertRule]:
    """Get alert rule by ID"""
    return db.query(AlertRule).filter_by(id=rule_id).first()


def list_active_alerts(db: Session, ticker: Optional[str] = None) -> List[AlertRule]:
    """List all active alert rules"""
    query = db.query(AlertRule).filter(
        and_(
            AlertRule.is_enabled == True,
            AlertRule.deleted_at == None
        )
    )
    
    if ticker:
        query = query.filter_by(ticker=ticker)
    
    return query.all()


def list_alerts_by_type(
    db: Session,
    alert_type: str,
    active_only: bool = True
) -> List[AlertRule]:
    """List alerts by type (PRICE, TECHNICAL, FUNDAMENTAL, RISK)"""
    query = db.query(AlertRule).filter_by(alert_type=alert_type)
    
    if active_only:
        query = query.filter(
            and_(
                AlertRule.is_enabled == True,
                AlertRule.deleted_at == None
            )
        )
    
    return query.all()


def update_alert_rule(
    db: Session,
    rule_id: int,
    **updates
) -> AlertRule:
    """Update alert rule"""
    rule = db.query(AlertRule).filter_by(id=rule_id).first()
    if not rule:
        raise ValueError(f"Alert rule {rule_id} not found")
    
    for key, value in updates.items():
        if hasattr(rule, key):
            setattr(rule, key, value)
    
    rule.updated_at = now_ist()
    db.commit()
    db.refresh(rule)
    return rule


def mark_alert_triggered(
    db: Session,
    rule_id: int
) -> AlertRule:
    """Mark alert as triggered"""
    rule = db.query(AlertRule).filter_by(id=rule_id).first()
    if not rule:
        raise ValueError(f"Alert rule {rule_id} not found")
    
    rule.last_triggered_at = now_ist()
    rule.trigger_count = (rule.trigger_count or 0) + 1
    db.commit()
    db.refresh(rule)
    logger.info(f"🔔 Alert triggered: {rule.name} (count: {rule.trigger_count})")
    return rule


def soft_delete_alert(
    db: Session,
    rule_id: int
) -> AlertRule:
    """Soft delete alert rule"""
    rule = db.query(AlertRule).filter_by(id=rule_id).first()
    if not rule:
        raise ValueError(f"Alert rule {rule_id} not found")
    
    rule.deleted_at = now_ist()
    rule.is_enabled = False
    db.commit()
    db.refresh(rule)
    logger.info(f"🗑️ Alert rule deleted: {rule.name}")
    return rule


def delete_alert_permanently(db: Session, rule_id: int) -> None:
    """Permanently delete alert rule"""
    rule = db.query(AlertRule).filter_by(id=rule_id).first()
    if not rule:
        raise ValueError(f"Alert rule {rule_id} not found")
    
    db.delete(rule)
    db.commit()
    logger.info(f"🗑️ Alert rule permanently deleted: {rule.name}")
