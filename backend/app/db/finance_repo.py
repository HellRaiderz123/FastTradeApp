from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta, date
from app.db.models_finance import (
    FinanceTransaction, RecurringTransaction, Budget, SavingsGoal,
    BillReminder, ExpenseForecast, CurrencyExchange
)
from app.api.schemas.finance import (
    FinanceTransactionCreate,
    FinanceTransactionUpdate,
    RecurringTransactionCreate,
    BudgetCreate,
    SavingsGoalCreate,
    BillReminderCreate,
)


# ============= TRANSACTIONS =============
def create_transactions(
    db: Session,
    items: list[FinanceTransactionCreate],
):
    objects = [FinanceTransaction(**item.dict()) for item in items]
    db.bulk_save_objects(objects)
    db.commit()
    return objects


def get_transactions(db: Session):
    return (
        db.query(FinanceTransaction)
        .order_by(FinanceTransaction.tran_date.desc())
        .all()
    )


def update_category(
    db: Session,
    tx_id: int,
    payload: FinanceTransactionUpdate,
):
    tx = db.query(FinanceTransaction).get(tx_id)
    if not tx:
        return None

    if payload.category:
        tx.category = payload.category

    db.commit()
    db.refresh(tx)
    return tx


def delete_all_transactions(db: Session):
    db.query(FinanceTransaction).delete()
    db.commit()


def delete_transaction(db: Session, tx_id: int):
    tx = db.query(FinanceTransaction).get(tx_id)
    if not tx:
        return False

    db.delete(tx)
    db.commit()
    return True


# ============= RECURRING TRANSACTIONS =============
def create_recurring_transaction(
    db: Session,
    payload: RecurringTransactionCreate,
):
    recurring = RecurringTransaction(**payload.dict())
    db.add(recurring)
    db.commit()
    db.refresh(recurring)
    return recurring


def get_recurring_transactions(db: Session):
    return (
        db.query(RecurringTransaction)
        .filter(RecurringTransaction.is_active == True)
        .all()
    )


def update_recurring_transaction(
    db: Session,
    recurring_id: int,
    is_active: bool,
):
    recurring = db.query(RecurringTransaction).get(recurring_id)
    if not recurring:
        return None

    recurring.is_active = is_active
    db.commit()
    db.refresh(recurring)
    return recurring


def delete_recurring_transaction(db: Session, recurring_id: int):
    recurring = db.query(RecurringTransaction).get(recurring_id)
    if not recurring:
        return False

    db.delete(recurring)
    db.commit()
    return True


# ============= BUDGETS =============
def create_budget(
    db: Session,
    payload: BudgetCreate,
):
    current_month = datetime.now().strftime("%Y-%m")
    budget = Budget(
        category=payload.category,
        monthly_limit=payload.monthly_limit,
        alert_threshold=payload.alert_threshold,
        month=current_month,
    )
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


def get_budgets(db: Session, month: str = None):
    query = db.query(Budget)
    if month:
        query = query.filter(Budget.month == month)
    else:
        current_month = datetime.now().strftime("%Y-%m")
        query = query.filter(Budget.month == current_month)
    
    return query.all()


def get_budget_status(db: Session, category: str, month: str = None):
    """Get budget status with spent amount"""
    if not month:
        month = datetime.now().strftime("%Y-%m")
    
    budget = db.query(Budget).filter(
        Budget.category == category,
        Budget.month == month
    ).first()
    
    if not budget:
        return None
    
    # Calculate spent amount in this month
    start_date = datetime.strptime(month + "-01", "%Y-%m-%d").date()
    if month.endswith("12"):
        next_month = datetime.strptime(str(int(month[:4]) + 1) + "-01-01", "%Y-%m-%d").date()
    else:
        next_month = datetime.strptime(month + "-01", "%Y-%m-%d").replace(month=int(month.split("-")[1]) + 1).date()
    
    spent = db.query(func.sum(FinanceTransaction.debit)).filter(
        FinanceTransaction.category == category,
        FinanceTransaction.tran_date >= start_date,
        FinanceTransaction.tran_date < next_month,
    ).scalar() or 0
    
    return {
        "budget": budget,
        "spent": spent,
        "remaining": budget.monthly_limit - spent,
        "percent_used": (spent / budget.monthly_limit * 100) if budget.monthly_limit > 0 else 0,
    }


def delete_budget(db: Session, budget_id: int):
    budget = db.query(Budget).get(budget_id)
    if not budget:
        return False

    db.delete(budget)
    db.commit()
    return True


# ============= SAVINGS GOALS =============
def create_savings_goal(
    db: Session,
    payload: SavingsGoalCreate,
):
    goal = SavingsGoal(**payload.dict())
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def get_savings_goals(db: Session):
    return db.query(SavingsGoal).all()


def update_savings_goal_amount(db: Session, goal_id: int, amount: float):
    goal = db.query(SavingsGoal).get(goal_id)
    if not goal:
        return None

    goal.current_amount = amount
    db.commit()
    db.refresh(goal)
    return goal


def delete_savings_goal(db: Session, goal_id: int):
    goal = db.query(SavingsGoal).get(goal_id)
    if not goal:
        return False

    db.delete(goal)
    db.commit()
    return True


# ============= BILL REMINDERS =============
def create_bill_reminder(
    db: Session,
    payload: BillReminderCreate,
):
    bill = BillReminder(**payload.dict())
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return bill


def get_bill_reminders(db: Session):
    return db.query(BillReminder).filter(BillReminder.is_paid == False).all()


def mark_bill_paid(db: Session, bill_id: int):
    bill = db.query(BillReminder).get(bill_id)
    if not bill:
        return None

    bill.is_paid = True
    db.commit()
    db.refresh(bill)
    return bill


def delete_bill_reminder(db: Session, bill_id: int):
    bill = db.query(BillReminder).get(bill_id)
    if not bill:
        return False

    db.delete(bill)
    db.commit()
    return True


# ============= EXPENSE FORECASTING =============
def calculate_expense_forecast(db: Session, category: str, months_back: int = 3):
    """Calculate forecast for next month based on history"""
    today = date.today()
    current_month = today.strftime("%Y-%m")
    
    # Get historical data
    start_date = today.replace(day=1) - timedelta(days=30 * months_back)
    
    historical = db.query(FinanceTransaction).filter(
        FinanceTransaction.category == category,
        FinanceTransaction.tran_date >= start_date,
    ).all()
    
    if not historical:
        return None
    
    # Calculate average
    total_spent = sum(t.debit for t in historical)
    avg_monthly = total_spent / months_back if months_back > 0 else 0
    
    # Simple forecast: average + 5% buffer
    predicted = avg_monthly * 1.05
    confidence = min(0.9, 0.5 + (len(historical) / 100))  # More data = more confidence
    
    # Check if forecast already exists
    existing = db.query(ExpenseForecast).filter(
        ExpenseForecast.category == category,
        ExpenseForecast.forecast_month == current_month,
    ).first()
    
    if existing:
        existing.predicted_amount = predicted
        existing.confidence = confidence
    else:
        forecast = ExpenseForecast(
            category=category,
            forecast_month=current_month,
            predicted_amount=predicted,
            confidence=confidence,
        )
        db.add(forecast)
    
    db.commit()
    return predicted


def get_expense_forecasts(db: Session, month: str = None):
    """Get all forecasts for a month or current month"""
    if not month:
        month = datetime.now().strftime("%Y-%m")
    
    return db.query(ExpenseForecast).filter(
        ExpenseForecast.forecast_month == month
    ).all()


def compute_category_trends(db: Session, months: int = 6, top_n: int = 5):
    """Return trend analysis for top spending categories over past `months` months.

    Result format:
    {
        "months": ["2025-09", ..., "2026-02"],
        "trends": [
            {
                "category": "Food",
                "months": [{"month":"2026-02","total":1234.0}, ...],
                "pct_change_last_month": 5.2,  # percent
                "slope": 12.3,  # raw slope from simple regression
                "trend": "increasing"|"decreasing"|"stable"
            }, ...
        ]
    }
    """
    today = date.today()
    current_month_start = today.replace(day=1)

    def shift_months(month_start: date, delta_months: int) -> date:
        total_months = month_start.year * 12 + (month_start.month - 1) + delta_months
        new_year = total_months // 12
        new_month = (total_months % 12) + 1
        return date(new_year, new_month, 1)

    # build months list oldest->newest using true calendar-month stepping
    month_starts = [shift_months(current_month_start, -offset) for offset in range(months - 1, -1, -1)]
    months_list = [month_start.strftime("%Y-%m") for month_start in month_starts]

    start_date = month_starts[0]

    # pick top categories by total spent in the period
    cat_rows = (
        db.query(FinanceTransaction.category, func.sum(FinanceTransaction.debit).label("total"))
        .filter(FinanceTransaction.tran_date >= start_date)
        .group_by(FinanceTransaction.category)
        .order_by(desc("total"))
        .limit(top_n)
        .all()
    )

    categories = [r[0] for r in cat_rows]
    result = []

    for cat in categories:
        monthly = []
        totals = []
        for m in months_list:
            year, mon = map(int, m.split("-"))
            from_dt = date(year, mon, 1)
            if mon == 12:
                to_dt = date(year + 1, 1, 1)
            else:
                to_dt = date(year, mon + 1, 1)

            s = db.query(func.coalesce(func.sum(FinanceTransaction.debit), 0)).filter(
                FinanceTransaction.category == cat,
                FinanceTransaction.tran_date >= from_dt,
                FinanceTransaction.tran_date < to_dt,
            ).scalar()
            s = float(s or 0)
            monthly.append({"month": m, "total": s})
            totals.append(s)

        # percent change last month vs previous
        pct_change = None
        if len(totals) >= 2:
            prev = totals[-2]
            last = totals[-1]
            pct_change = ((last - prev) / prev * 100) if prev != 0 else None

        # simple slope (least squares) over months
        slope = 0.0
        if len(totals) >= 2:
            xs = list(range(len(totals)))
            n = len(xs)
            mean_x = sum(xs) / n
            mean_y = sum(totals) / n
            num = sum((xs[i] - mean_x) * (totals[i] - mean_y) for i in range(n))
            den = sum((xs[i] - mean_x) ** 2 for i in range(n))
            slope = (num / den) if den != 0 else 0.0

        trend = "stable"
        if pct_change is not None:
            if pct_change > 5:
                trend = "increasing"
            elif pct_change < -5:
                trend = "decreasing"

        result.append(
            {
                "category": cat,
                "months": monthly,
                "pct_change_last_month": pct_change,
                "slope": slope,
                "trend": trend,
            }
        )

    return {"months": months_list, "trends": result}


# ============= CURRENCY EXCHANGE =============
def update_exchange_rate(db: Session, from_cur: str, to_cur: str, rate: float):
    """Update or create exchange rate"""
    exchange = db.query(CurrencyExchange).filter(
        CurrencyExchange.from_currency == from_cur,
        CurrencyExchange.to_currency == to_cur,
    ).first()
    
    if exchange:
        exchange.rate = rate
        exchange.updated_at = datetime.utcnow()
    else:
        exchange = CurrencyExchange(
            from_currency=from_cur,
            to_currency=to_cur,
            rate=rate,
        )
        db.add(exchange)
    
    db.commit()
    db.refresh(exchange)
    return exchange


def get_exchange_rate(db: Session, from_cur: str, to_cur: str):
    """Get exchange rate"""
    return db.query(CurrencyExchange).filter(
        CurrencyExchange.from_currency == from_cur,
        CurrencyExchange.to_currency == to_cur,
    ).first()


def get_all_exchange_rates(db: Session):
    """Get all exchange rates"""
    return db.query(CurrencyExchange).all()
