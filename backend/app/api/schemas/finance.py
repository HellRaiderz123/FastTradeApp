from datetime import date, datetime
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
        from_attributes = True


# Recurring Transactions
class RecurringTransactionCreate(BaseModel):
    description: str
    amount: float
    category: str
    frequency: str  # daily, weekly, monthly, yearly
    start_date: date
    end_date: Optional[date] = None


class RecurringTransactionOut(BaseModel):
    id: int
    description: str
    amount: float
    category: str
    frequency: str
    start_date: date
    end_date: Optional[date]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Budget
class BudgetCreate(BaseModel):
    category: str
    monthly_limit: float
    alert_threshold: float = 80


class BudgetOut(BaseModel):
    id: int
    category: str
    monthly_limit: float
    alert_threshold: float
    month: str
    created_at: datetime

    class Config:
        from_attributes = True


# Savings Goal
class SavingsGoalCreate(BaseModel):
    name: str
    target_amount: float
    deadline: date
    category: Optional[str] = None
    priority: str = "medium"


class SavingsGoalOut(BaseModel):
    id: int
    name: str
    target_amount: float
    current_amount: float
    deadline: date
    category: Optional[str]
    priority: str
    progress_percent: float  # Calculated field
    days_remaining: int  # Calculated field
    created_at: datetime

    class Config:
        from_attributes = True


# Bill Reminder
class BillReminderCreate(BaseModel):
    name: str
    amount: float
    due_date: date
    category: str
    reminder_days: int = 3


class BillReminderOut(BaseModel):
    id: int
    name: str
    amount: float
    due_date: date
    category: str
    is_paid: bool
    reminder_days: int
    days_until_due: int  # Calculated
    is_overdue: bool  # Calculated
    created_at: datetime

    class Config:
        from_attributes = True


# Expense Forecast
class ExpenseForecastOut(BaseModel):
    id: int
    category: str
    forecast_month: str
    predicted_amount: float
    confidence: float
    actual_amount: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


# Currency Exchange
class CurrencyExchangeOut(BaseModel):
    id: int
    from_currency: str
    to_currency: str
    rate: float
    updated_at: datetime

    class Config:
        from_attributes = True
