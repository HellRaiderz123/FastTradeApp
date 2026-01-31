from datetime import date
from typing import Optional
from pydantic import BaseModel


class FinanceTransactionCreate(BaseModel):
    tran_date: date
    description: str
    debit: float = 0
    credit: float = 0
    balance: float = 0
    category: str = "Uncategorized"
    source: str = "AXIS"


class FinanceTransactionUpdate(BaseModel):
    category: Optional[str] = None


class FinanceTransactionOut(BaseModel):
    id: int
    tran_date: date
    description: str
    debit: float
    credit: float
    balance: float
    category: str
    source: str

    class Config:
        orm_mode = True
