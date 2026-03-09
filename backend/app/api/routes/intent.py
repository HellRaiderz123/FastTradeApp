from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import cast, Optional
import logging

from app.db.session import SessionLocal
from app.db.intent_repo import create_execution_intent
from app.db.models import StrategyRun
from app.db.models_intent import ExecutionIntent

from app.core.risk.trade_limit import check_daily_trade_limit
from app.core.risk.system_guard import is_trading_enabled
from app.core.risk.tp_sl_calculator import (
    calculate_tp_sl_from_ticket,
    get_risk_percentage_from_mode,
    get_risk_percentage_from_settings,
)
from app.core.risk.risk_limits_config import get_risk_limits
from app.core.broker.zerodha.client import get_kite_client
from app.core.learning.signal_diagnostics import record_entry_snapshot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/intent", tags=["Execution Intent"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# PATCH endpoint to update TP/SL/trailing for an existing intent
@router.patch("/{intent_id}/update_tp_sl")
def update_tp_sl(
    intent_id: str,
    tp: Optional[float] = Body(None),
    sl: Optional[float] = Body(None),
    trailing_sl: Optional[float] = Body(None),
    db: Session = Depends(get_db)
):
    intent = db.query(ExecutionIntent).filter(ExecutionIntent.intent_id == intent_id).first()
    if not intent:
        raise HTTPException(status_code=404, detail="Intent not found")
    if tp is not None:
        intent.tp = tp
    if sl is not None:
        intent.sl = sl
    if trailing_sl is not None:
        intent.trailing_sl_pct = trailing_sl
    db.commit()
    db.refresh(intent)
    return {"success": True, "tp": intent.tp, "sl": intent.sl, "trailing_sl": intent.trailing_sl_pct}

@router.post("/create")
def create_intent(
    run_id: int,
    capital: Optional[float] = None,
    risk_mode: Optional[str] = None,
    risk_profile: Optional[str] = None,  # Can override with 'conservative', 'balanced', 'aggressive'
    db: Session = Depends(get_db)
):
    """
    Create execution intent with configurable risk parameters.
    
    Args:
        run_id: Strategy run ID
        capital: Available capital for this trade (if None, fetches from Zerodha)
        risk_mode: Risk mode for TP/SL calculation (CONSERVATIVE/BALANCED/AGGRESSIVE).
                   If not provided, uses risk percentage from Settings
        risk_profile: Risk profile for trade limits (conservative/balanced/aggressive)
        db: Database session
    """
    # 🔹 Fetch real capital from Zerodha if not provided
    if capital is None:
        try:
            kite = get_kite_client()
            margins = kite.margins()
            capital = margins["equity"]["available"]["live_balance"]
            logger.info(f"📊 Fetched capital from Zerodha: ₹{capital}")
        except Exception as e:
            logger.error(f"Failed to fetch capital from Zerodha: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch account capital: {str(e)}"
            )
    
    # 🔒 Manual kill switch
    if not is_trading_enabled(db):
        raise HTTPException(
            status_code=403,
            detail="Trading is disabled by system kill switch",
        )

    run = db.query(StrategyRun).filter(StrategyRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Strategy run not found")

    # SQLAlchemy-safe boolean check
    if run.approved is not True:
        raise HTTPException(status_code=400, detail="Strategy not approved")

    if run.ticket is None:
        raise HTTPException(
            status_code=400,
            detail="No executable ticket available for this run",
        )

    # Get risk configuration based on profile
    risk_config = get_risk_limits(profile=risk_profile)

    # 🔒 Daily trade limit guard with configurable limit
    if check_daily_trade_limit(db, risk_config=risk_config):
        raise HTTPException(
            status_code=429,
            detail=f"Daily trade limit of {risk_config.max_trades_per_day} reached",
        )

    # 💡 Calculate dynamic TP/SL: Use database setting if risk_mode not explicitly provided
    if risk_mode:
        # User explicitly provided a risk mode, use that profile
        risk_pct = get_risk_percentage_from_mode(risk_mode)
    else:
        # No explicit risk mode → use risk percentage from Settings (max_portfolio_loss_pct)
        risk_pct = get_risk_percentage_from_settings(db)
    
    tp_sl = calculate_tp_sl_from_ticket(
        ticket=run.ticket,
        capital=capital,
        risk_percentage=risk_pct,
    )

    # Extract expiry from context (if available)
    expiry = None
    if run.context and isinstance(run.context, dict):
        expiry = run.context.get("expiry")
    
    # If expiry not in context, try to get current weekly expiry as fallback
    if not expiry:
        from app.core.market.expiry import get_current_weekly_expiry
        try:
            expiry = get_current_weekly_expiry(run.underlying)
            logger.info(f"📅 Expiry not in context, using current weekly expiry: {expiry} for {run.underlying}")
        except Exception as e:
            logger.warning(f"⚠️  Could not determine expiry for {run.underlying}: {e}")
            # Let execution adapter handle missing expiry

    # Extract trailing_sl_pct from strategy configuration (if available)
    # Note: StrategyRun doesn't have strategy_config relationship, so we safely default to None
    trailing_sl_pct = None

    intent = create_execution_intent(
        db=db,
        run_id=cast(int, run.id),
        strategy=str(run.strategy),
        underlying=str(run.underlying),
        ticket=run.ticket,
        expiry=expiry,
        tp=tp_sl["tp"],     # Dynamic TP
        sl=tp_sl["sl"],     # Dynamic SL
        trailing_sl_pct=trailing_sl_pct,  # Will be None unless strategy explicitly sets it
    )

    # 📊 Record signal snapshot for diagnostics
    # Reconstruct engine_result from StrategyRun signal/context for signal diagnostics
    try:
        engine_result = {
            "signal": run.signal or {},
            "context": run.context or {},
        }
        record_entry_snapshot(db, intent=intent, engine_result=engine_result)
    except Exception as e:
        logger.warning(f"Failed to record entry snapshot for intent {intent.intent_id}: {e}")

    return {
        "intent_id": intent.intent_id,
        "status": intent.status,
        "expires_at": intent.expires_at,
        "tp_sl": tp_sl,  # Include calculated TP/SL in response
        "risk_limits": {
            "max_portfolio_loss_pct": risk_config.max_portfolio_loss_pct,
            "max_trades_per_day": risk_config.max_trades_per_day,
        }
    }


@router.get("/{intent_id}")
def get_intent_status(intent_id: str, db: Session = Depends(get_db)):
    """
    Fetch current status of an execution intent.
    SAFE: Read-only, no side effects.
    """
    intent = (
        db.query(ExecutionIntent)
        .filter(ExecutionIntent.intent_id == intent_id)
        .first()
    )

    if intent is None:
        raise HTTPException(status_code=404, detail="Intent not found")

    return {
        "intent_id": intent.intent_id,
        "run_id": intent.run_id,
        "strategy": intent.strategy,
        "underlying": intent.underlying,
        "status": intent.status,
        "execution": intent.execution_result,
        "created_at": intent.created_at,
        "expires_at": intent.expires_at,
    }
