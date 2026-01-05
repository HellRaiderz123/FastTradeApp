from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.core.strategies.option_spread_15m.engine import run_option_spread
from app.db.models import StrategyRun
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================
# REQUEST MODEL
# ============================

class OptionSpreadRequest(BaseModel):
    underlying: str
    interval: str = "15minute"
    use_ml: bool = True
    min_confidence: float = 75
    risk_mode: str = "Conservative"
    lots: int = 1
    capital: float


# ============================
# RESPONSE MODEL (loose)
# ============================

class OptionSpreadResponse(BaseModel):
    run_id: Optional[int] = None
    strategy: str
    approved: bool
    reason: str
    ticket: Optional[Dict[str, Any]] = None
    risk_metrics: Optional[Dict[str, Any]] = None
    signal: Dict[str, Any]
    context: Dict[str, Any]
    spot: Optional[float] = None
    atm: Optional[int] = None
    strike_meta: Optional[Dict[str, Any]] = None


# ============================
# API ENDPOINT
# ============================

@router.post(
    "/option-spread/15m/run",
    response_model=OptionSpreadResponse,
)
def run_option_spread_api(payload: OptionSpreadRequest,  db: Session = Depends(get_db),):
    """
    Run 15m Option Spread strategy (Bull Put / Bear Call).

    SAFE:
    - No execution
    - No broker keys
    - Backend-only logic
    """

    try:
        result = run_option_spread(db=db, payload=payload.dict())
        return result


    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Strategy engine error: {str(e)}",
        )
