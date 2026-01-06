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
