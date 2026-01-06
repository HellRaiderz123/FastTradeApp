"""
Phase 2 API Routes: Registry-Based Strategy Execution

New endpoints for executing strategies via StrategyRegistry (v2).
Coexists with legacy /execute/paper endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.core.strategies.executor import StrategyExecutor, MultiStrategyExecutor

router = APIRouter(prefix="/strategies/run", tags=["Strategy Execution"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================
# REQUEST MODELS
# ============================

class ExecuteStrategyRequest(BaseModel):
    """Request to execute a single strategy"""
    strategy_id: int
    additional_context: Optional[Dict[str, Any]] = None


class ExecuteMultipleRequest(BaseModel):
    """Request to execute multiple strategies"""
    strategy_ids: Optional[List[int]] = None  # If None, execute all enabled
    additional_context: Optional[Dict[str, Any]] = None


# ============================
# ENDPOINTS
# ============================

@router.post(
    "/single",
    summary="Execute single strategy by ID"
)
def execute_single_strategy(
    request: ExecuteStrategyRequest,
    db: Session = Depends(get_db),
):
    """
    Execute a single strategy using database configuration.
    
    Returns the strategy execution result.
    """
    try:
        executor = StrategyExecutor(request.strategy_id, db)
        
        if not executor.load_config():
            raise HTTPException(
                status_code=404,
                detail=f"Strategy {request.strategy_id} not found or not enabled"
            )
        
        result = executor.execute(request.additional_context)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/all",
    summary="Execute all enabled strategies in parallel"
)
def execute_all_enabled(
    request: ExecuteMultipleRequest,
    db: Session = Depends(get_db),
):
    """
    Execute all enabled strategies in parallel.
    
    Results are aggregated and returned.
    """
    try:
        executor = MultiStrategyExecutor(db)
        result = executor.execute_parallel(request.additional_context)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/multiple",
    summary="Execute specific strategies by ID"
)
def execute_multiple_strategies(
    request: ExecuteMultipleRequest,
    db: Session = Depends(get_db),
):
    """
    Execute specific strategies by their IDs in parallel.
    """
    if not request.strategy_ids or len(request.strategy_ids) == 0:
        raise HTTPException(
            status_code=400,
            detail="strategy_ids required"
        )
    
    try:
        executor = MultiStrategyExecutor(db)
        result = executor.execute_specific(
            request.strategy_ids,
            request.additional_context
        )
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{strategy_id}/status"
)
def get_strategy_status(
    strategy_id: int,
    db: Session = Depends(get_db),
):
    """Check if strategy is enabled and ready for execution"""
    try:
        from app.db.models import StrategyConfig
        
        config = db.query(StrategyConfig).filter_by(id=strategy_id).first()
        
        if not config:
            raise HTTPException(status_code=404, detail="Strategy not found")
        
        return {
            "id": strategy_id,
            "name": config.name,
            "enabled": config.enabled,
            "type": config.strategy_type,
            "underlying": config.underlying,
            "ready": config.enabled,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
