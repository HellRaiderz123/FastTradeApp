from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.core.strategies.option_spread_15m.engine import run_option_spread
from app.db.models import StrategyRun
from app.db.session import SessionLocal

router = APIRouter()


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
def run_option_spread_api(payload: OptionSpreadRequest):
    """
    Run 15m Option Spread strategy (Bull Put / Bear Call).

    SAFE:
    - No execution
    - No broker keys
    - Backend-only logic
    """

    try:
        result = run_option_spread(payload.dict())
        # Attach run_id from DB (latest run)
        db = SessionLocal()
        try:
            last_run = (
                db.query(StrategyRun)
                .order_by(StrategyRun.id.desc())
                .first()
            )
            if last_run:
                result["run_id"] = last_run.id
        finally:
            db.close()

        return result


    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Strategy engine error: {str(e)}",
        )
