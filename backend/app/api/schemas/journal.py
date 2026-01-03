from pydantic import BaseModel
from datetime import datetime
from typing import Optional


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
        orm_mode = True
