from sqlalchemy import Column, Integer, String, Float, Date, Boolean, DateTime
from datetime import datetime
from app.db.models import Base


class FinanceTransaction(Base):
    __tablename__ = "finance_transactions"

    id = Column(Integer, primary_key=True, index=True)

    tran_date = Column(Date, nullable=False)
    description = Column(String, nullable=False)

    debit = Column(Float, default=0)
    credit = Column(Float, default=0)
    balance = Column(Float, default=0)

    category = Column(String, default="Uncategorized")
    source = Column(String, default="AXIS")  # AXIS / HDFC / ICICI


class RecurringTransaction(Base):
    __tablename__ = "recurring_transactions"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=False)
    frequency = Column(String, nullable=False)  # daily, weekly, monthly, yearly
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)  # None for ongoing
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False)
    monthly_limit = Column(Float, nullable=False)
    alert_threshold = Column(Float, default=80)  # Alert at 80% spent
    month = Column(String, nullable=False)  # YYYY-MM format
    created_at = Column(DateTime, default=datetime.utcnow)


class SavingsGoal(Base):
    __tablename__ = "savings_goals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    target_amount = Column(Float, nullable=False)
    current_amount = Column(Float, default=0)
    deadline = Column(Date, nullable=False)
    category = Column(String, nullable=True)
    priority = Column(String, default="medium")  # high, medium, low
    created_at = Column(DateTime, default=datetime.utcnow)


class BillReminder(Base):
    __tablename__ = "bill_reminders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    due_date = Column(Date, nullable=False)
    category = Column(String, nullable=False)
    is_paid = Column(Boolean, default=False)
    reminder_days = Column(Integer, default=3)  # Remind N days before due
    created_at = Column(DateTime, default=datetime.utcnow)


class ExpenseForecast(Base):
    __tablename__ = "expense_forecasts"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False)
    forecast_month = Column(String, nullable=False)  # YYYY-MM
    predicted_amount = Column(Float, nullable=False)
    confidence = Column(Float)  # 0-1 confidence score
    actual_amount = Column(Float, nullable=True)  # Filled after month ends
    created_at = Column(DateTime, default=datetime.utcnow)


class CurrencyExchange(Base):
    __tablename__ = "currency_exchanges"

    id = Column(Integer, primary_key=True, index=True)
    from_currency = Column(String, nullable=False)  # INR, USD, EUR, etc.
    to_currency = Column(String, nullable=False)
    rate = Column(Float, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)
