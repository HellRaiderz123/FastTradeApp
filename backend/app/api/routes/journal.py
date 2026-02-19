from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List
import logging
from datetime import datetime

from app.db.session import SessionLocal
from app.db.queries import get_recent_strategy_runs
from app.db.models_intent import ExecutionIntent
from app.api.schemas.journal import StrategyRunOut, ExecutionIntentOut
from app.core.utils.time import now_ist
from app.core.broker.zerodha.client import get_kite_client
from app.services.zerodha_ticker import subscribe_symbols as subscribe_to_ticker

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
            existing = db.query(ExecutionIntent).filter(
                ExecutionIntent.status == "EXECUTED",
                ExecutionIntent.closed_at.is_(None)
            ).all()
            
            # Look for a match: symbol in ticket.legs
            found = False
            for intent in existing:
                ticket = intent.ticket or {}
                legs = ticket.get("legs", [])
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
    try:
        _sync_zerodha_live_positions(db)
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
