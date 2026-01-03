# backend/app/core/option_spread_15m/models.py
from pydantic import BaseModel
from typing import List, Optional

class SpreadLeg(BaseModel):
    side: str           # BUY / SELL
    symbol: str
    strike: int
    opt_type: str       # PE / CE

class SpreadTicket(BaseModel):
    strategy: str       # BULL_PUT / BEAR_CALL
    underlying: str
    lot_size: int
    lots: int
    legs: List[SpreadLeg]

class StrategyResult(BaseModel):
    strategy_mode: str
    approved: bool
    reason: str
    ticket: Optional[SpreadTicket]
    metrics: dict
    blocked_by: List[str]
