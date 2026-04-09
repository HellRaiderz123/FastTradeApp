from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any


class StrategyRunOut(BaseModel):
    id: int
    strategy: str
    underlying: str
    approved: bool
    reason: str

    risk_pct: Optional[float]
    max_loss: Optional[float]

    created_at: datetime

    class Config:
        from_attributes = True


class ExecutionIntentOut(BaseModel):
    id: int
    intent_id: str
    run_id: int
    strategy: str
    underlying: str
    status: str
    executed: bool
    ticket: Optional[Any]
    
    avg_price: Optional[float]
    pnl: Optional[float]
    unrealized_pnl: Optional[float]
    
    tp: Optional[float]
    sl: Optional[float]
    exit_reason: Optional[str]
    
    entry_credit: Optional[float]
    margin_required: Optional[float]
    execution_result: Optional[Any]  # Contains mode, orders, timestamps, etc.
    created_at: datetime
    closed_at: Optional[datetime]
    
    class Config:
        from_attributes = True
