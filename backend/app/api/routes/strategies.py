"""
Strategy Management API Endpoints
CRUD operations for strategy configurations
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.db.session import SessionLocal
from app.db.models import StrategyConfig
from app.core.utils.time import now_ist
from pydantic import BaseModel

router = APIRouter(prefix="/strategies", tags=["Strategies"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ====== SCHEMAS ======

class StrategyConfigSchema(BaseModel):
    name: str
    description: Optional[str] = None
    strategy_type: str  # option_spread_15m, etc.
    underlying: str  # NIFTY, BANKNIFTY, FINNIFTY
    parameters: dict  # {risk_mode, lots, capital_percent, etc.}


class StrategyConfigResponseSchema(StrategyConfigSchema):
    id: int
    enabled: bool
    deployed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    created_by: str

    class Config:
        from_attributes = True


# ====== ENDPOINTS ======


class CreateFromSuggestionRequest(BaseModel):
    """Request to create a strategy from a trade suggestion"""
    underlying: str
    strategy_type: str  # BULL_PUT, BEAR_CALL, BUTTERFLY_SPREAD, etc.
    reason: str
    confidence: float
    capital: float = 100000
    lots: int = 1
    risk_mode: str = "Conservative"
    min_confidence: float = 75
    spot: Optional[float] = None
    atm: Optional[float] = None
    ticket: Optional[dict] = None       # {legs: [{side, strike, type}, ...]}
    risk_metrics: Optional[dict] = None  # {risk_pct_capital, max_loss, ...}


@router.post("/create-from-suggestion", response_model=StrategyConfigResponseSchema)
def create_strategy_from_suggestion(
    request: CreateFromSuggestionRequest,
    db: Session = Depends(get_db)
):
    """
    Auto-create a strategy config from a trade suggestion.
    
    This bridges the gap between getting a suggestion (e.g., BUTTERFLY_SPREAD)
    and having a deployable strategy config in the database.
    """
    
    # Generate a unique name for the strategy
    timestamp = now_ist().strftime("%Y%m%d_%H%M%S")
    strategy_name = f"{request.underlying}_{request.strategy_type}_{timestamp}"
    
    # Check if this exact name exists (unlikely with timestamp, but be safe)
    counter = 1
    original_name = strategy_name
    while db.query(StrategyConfig).filter(StrategyConfig.name == strategy_name).first():
        strategy_name = f"{original_name}_{counter}"
        counter += 1
    
    # Map strategy type to strategy_type used by the engine
    strategy_type_mapping = {
        "BULL_PUT": "option_spread_15m",
        "BEAR_CALL": "option_spread_15m",
        "BULL_CALL": "option_spread_15m",
        "BEAR_PUT": "option_spread_15m",
        "IRON_CONDOR": "option_spread_15m",
        "BUTTERFLY_SPREAD": "option_spread_15m",
        "SHORT_STRADDLE": "option_spread_15m",
        "LONG_STRADDLE": "option_spread_15m",
        "SHORT_STRANGLE": "option_spread_15m",
        "LONG_STRANGLE": "option_spread_15m",
        "CALL_RATIO_BACKSPREAD": "option_spread_15m",
        "PUT_RATIO_BACKSPREAD": "option_spread_15m",
    }
    
    engine_strategy_type = strategy_type_mapping.get(request.strategy_type, "option_spread_15m")
    
    # Build parameters
    parameters = {
        "interval": "15minute",
        "risk_mode": request.risk_mode,
        "lots": request.lots,
        "capital": request.capital,
        "min_confidence": request.min_confidence,
        "use_ml": False,
        "preferred_strategy": request.strategy_type,
    }
    
    # Include spot/ATM snapshot
    if request.spot:
        parameters["spot_at_creation"] = request.spot
    if request.atm:
        parameters["atm_at_creation"] = request.atm
    
    # Include ticket legs from suggestion
    if request.ticket and isinstance(request.ticket, dict):
        raw_legs = request.ticket.get("legs", [])
        if raw_legs:
            lot_size = request.ticket.get("lot_size", 1)
            parameters["legs"] = [
                {
                    "type": leg.get("side", "BUY"),
                    "option_type": leg.get("type", "CE"),
                    "strike": leg.get("strike", 0),
                    "strike_type": "ABSOLUTE",
                    "strike_offset": 0,
                    "quantity": request.lots * lot_size,
                    "premium": leg.get("premium", 0),
                }
                for leg in raw_legs
            ]
            parameters["lot_size"] = lot_size
    
    # Include risk metrics
    if request.risk_metrics and isinstance(request.risk_metrics, dict):
        parameters["risk_metrics"] = request.risk_metrics
    
    # Create the description
    description = f"Auto-created from suggestion: {request.reason} (Confidence: {request.confidence:.1f}%)"
    
    strategy_config = StrategyConfig(
        name=strategy_name,
        description=description,
        strategy_type=engine_strategy_type,
        underlying=request.underlying,
        parameters=parameters,
        enabled=False,  # User must enable manually
        created_by="auto_suggestion"
    )
    
    db.add(strategy_config)
    db.commit()
    db.refresh(strategy_config)
    
    return strategy_config


@router.post("", response_model=StrategyConfigResponseSchema)
def create_strategy(
    config: StrategyConfigSchema,
    db: Session = Depends(get_db)
):
    """Create a new strategy configuration"""
    
    # Check if name already exists
    existing = db.query(StrategyConfig).filter(StrategyConfig.name == config.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Strategy '{config.name}' already exists")
    
    strategy_config = StrategyConfig(
        name=config.name,
        description=config.description,
        strategy_type=config.strategy_type,
        underlying=config.underlying,
        parameters=config.parameters,
        enabled=False,
        created_by="system"
    )
    
    db.add(strategy_config)
    db.commit()
    db.refresh(strategy_config)
    
    return strategy_config


@router.get("", response_model=List[StrategyConfigResponseSchema])
def list_strategies(
    enabled_only: bool = False,
    db: Session = Depends(get_db)
):
    """List all strategies or only enabled ones"""
    query = db.query(StrategyConfig)
    
    if enabled_only:
        query = query.filter(StrategyConfig.enabled == True)
    
    strategies = query.order_by(StrategyConfig.created_at.desc()).all()
    return strategies


@router.get("/{strategy_id}", response_model=StrategyConfigResponseSchema)
def get_strategy(
    strategy_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific strategy"""
    strategy = db.query(StrategyConfig).filter(StrategyConfig.id == strategy_id).first()
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    return strategy


@router.put("/{strategy_id}", response_model=StrategyConfigResponseSchema)
def update_strategy(
    strategy_id: int,
    config: StrategyConfigSchema,
    db: Session = Depends(get_db)
):
    """Update a strategy configuration"""
    strategy = db.query(StrategyConfig).filter(StrategyConfig.id == strategy_id).first()
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    # If enabled, prevent name changes
    if strategy.enabled and strategy.name != config.name:
        raise HTTPException(status_code=400, detail="Cannot rename deployed strategy")
    
    strategy.name = config.name
    strategy.description = config.description
    strategy.strategy_type = config.strategy_type
    strategy.underlying = config.underlying
    strategy.parameters = config.parameters
    strategy.updated_at = now_ist()
    
    db.commit()
    db.refresh(strategy)
    
    return strategy


@router.post("/{strategy_id}/enable")
def enable_strategy(
    strategy_id: int,
    db: Session = Depends(get_db)
):
    """Deploy/enable a strategy"""
    strategy = db.query(StrategyConfig).filter(StrategyConfig.id == strategy_id).first()
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    if strategy.enabled:
        return {"message": "Strategy already enabled", "strategy": strategy}
    
    strategy.enabled = True
    strategy.deployed_at = now_ist()
    strategy.updated_at = now_ist()
    
    db.commit()
    db.refresh(strategy)
    
    return {
        "message": f"Strategy '{strategy.name}' deployed successfully",
        "strategy": strategy
    }


@router.post("/{strategy_id}/disable")
def disable_strategy(
    strategy_id: int,
    db: Session = Depends(get_db)
):
    """Disable a strategy"""
    strategy = db.query(StrategyConfig).filter(StrategyConfig.id == strategy_id).first()
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    if not strategy.enabled:
        return {"message": "Strategy already disabled", "strategy": strategy}
    
    strategy.enabled = False
    strategy.deployed_at = None
    strategy.updated_at = now_ist()
    
    db.commit()
    db.refresh(strategy)
    
    return {
        "message": f"Strategy '{strategy.name}' disabled",
        "strategy": strategy
    }


@router.delete("/{strategy_id}")
def delete_strategy(
    strategy_id: int,
    db: Session = Depends(get_db)
):
    """Delete a strategy (cannot delete deployed ones)"""
    strategy = db.query(StrategyConfig).filter(StrategyConfig.id == strategy_id).first()
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    if strategy.enabled:
        raise HTTPException(status_code=400, detail="Cannot delete deployed strategy. Disable first.")
    
    db.delete(strategy)
    db.commit()
    
    return {"message": f"Strategy '{strategy.name}' deleted"}


@router.get("/{strategy_id}/status")
def get_strategy_status(
    strategy_id: int,
    db: Session = Depends(get_db)
):
    """Get strategy deployment status"""
    strategy = db.query(StrategyConfig).filter(StrategyConfig.id == strategy_id).first()
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    return {
        "id": strategy.id,
        "name": strategy.name,
        "enabled": strategy.enabled,
        "deployed_at": strategy.deployed_at,
        "strategy_type": strategy.strategy_type,
        "underlying": strategy.underlying
    }
