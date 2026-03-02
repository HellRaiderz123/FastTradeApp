from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date, timedelta
from app.db.session import SessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from app.db.finance_repo import (
    create_transactions,
    delete_transaction,
    get_transactions,
    update_category,
    delete_all_transactions,
    create_recurring_transaction,
    get_recurring_transactions,
    update_recurring_transaction,
    delete_recurring_transaction,
    create_budget,
    get_budgets,
    get_budget_status,
    delete_budget,
    create_savings_goal,
    get_savings_goals,
    update_savings_goal_amount,
    delete_savings_goal,
    create_bill_reminder,
    get_bill_reminders,
    mark_bill_paid,
    delete_bill_reminder,
    calculate_expense_forecast,
    get_expense_forecasts,
    compute_category_trends,
    update_exchange_rate,
    get_exchange_rate,
    get_all_exchange_rates,
)
from app.api.schemas.finance import (
    FinanceTransactionCreate,
    FinanceTransactionUpdate,
    FinanceTransactionOut,
    RecurringTransactionCreate,
    RecurringTransactionOut,
    BudgetCreate,
    BudgetOut,
    SavingsGoalCreate,
    SavingsGoalOut,
    BillReminderCreate,
    BillReminderOut,
    ExpenseForecastOut,
    CurrencyExchangeOut,
)

router = APIRouter(prefix="/finance", tags=["Finance"])


# ============= TRANSACTIONS =============
@router.post("/transactions")
def bulk_create_transactions(
    payload: list[FinanceTransactionCreate],
    db: Session = Depends(get_db),
):
    create_transactions(db, payload)
    return {"status": "ok", "count": len(payload)}


@router.get("/transactions", response_model=list[FinanceTransactionOut])
def list_transactions(db: Session = Depends(get_db)):
    return get_transactions(db)


@router.patch("/transactions/{tx_id}", response_model=FinanceTransactionOut)
def change_category(
    tx_id: int,
    payload: FinanceTransactionUpdate,
    db: Session = Depends(get_db),
):
    tx = update_category(db, tx_id, payload)
    if not tx:
        raise HTTPException(404, "Transaction not found")
    return tx


@router.delete("/transactions")
def clear_all(db: Session = Depends(get_db)):
    delete_all_transactions(db)
    return {"status": "ok"}


@router.delete("/transactions/{tx_id}")
def delete_single_transaction(
    tx_id: int,
    db: Session = Depends(get_db),
):
    success = delete_transaction(db, tx_id)
    if not success:
        raise HTTPException(404, "Transaction not found")
    return {"status": "deleted"}


# ============= RECURRING TRANSACTIONS =============
@router.post("/recurring", response_model=RecurringTransactionOut)
def add_recurring_transaction(
    payload: RecurringTransactionCreate,
    db: Session = Depends(get_db),
):
    return create_recurring_transaction(db, payload)


@router.get("/recurring", response_model=list[RecurringTransactionOut])
def list_recurring_transactions(db: Session = Depends(get_db)):
    return get_recurring_transactions(db)


@router.patch("/recurring/{recurring_id}")
def toggle_recurring_transaction(
    recurring_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
):
    recurring = update_recurring_transaction(db, recurring_id, is_active)
    if not recurring:
        raise HTTPException(404, "Recurring transaction not found")
    return recurring


@router.delete("/recurring/{recurring_id}")
def remove_recurring_transaction(
    recurring_id: int,
    db: Session = Depends(get_db),
):
    success = delete_recurring_transaction(db, recurring_id)
    if not success:
        raise HTTPException(404, "Recurring transaction not found")
    return {"status": "deleted"}


# ============= BUDGETS =============
@router.post("/budgets", response_model=BudgetOut)
def create_new_budget(
    payload: BudgetCreate,
    db: Session = Depends(get_db),
):
    return create_budget(db, payload)


@router.get("/budgets", response_model=list[BudgetOut])
def list_budgets(month: str = None, db: Session = Depends(get_db)):
    return get_budgets(db, month)


@router.get("/budgets/status/{category}")
def get_budget_spending(
    category: str,
    month: str = None,
    db: Session = Depends(get_db),
):
    status = get_budget_status(db, category, month)
    if not status:
        raise HTTPException(404, "Budget not found")
    return status


@router.delete("/budgets/{budget_id}")
def remove_budget(
    budget_id: int,
    db: Session = Depends(get_db),
):
    success = delete_budget(db, budget_id)
    if not success:
        raise HTTPException(404, "Budget not found")
    return {"status": "deleted"}


# ============= SAVINGS GOALS =============
@router.post("/goals", response_model=SavingsGoalOut)
def add_savings_goal(
    payload: SavingsGoalCreate,
    db: Session = Depends(get_db),
):
    return create_savings_goal(db, payload)


@router.get("/goals", response_model=list[SavingsGoalOut])
def list_savings_goals(db: Session = Depends(get_db)):
    goals = get_savings_goals(db)
    # Add calculated fields
    result = []
    for goal in goals:
        progress = (goal.current_amount / goal.target_amount * 100) if goal.target_amount > 0 else 0
        days_left = (goal.deadline - date.today()).days
        result.append({
            **goal.__dict__,
            "progress_percent": progress,
            "days_remaining": days_left,
        })
    return result


@router.patch("/goals/{goal_id}")
def update_goal_progress(
    goal_id: int,
    amount: float,
    db: Session = Depends(get_db),
):
    goal = update_savings_goal_amount(db, goal_id, amount)
    if not goal:
        raise HTTPException(404, "Savings goal not found")
    
    progress = (goal.current_amount / goal.target_amount * 100) if goal.target_amount > 0 else 0
    days_left = (goal.deadline - date.today()).days
    return {
        **goal.__dict__,
        "progress_percent": progress,
        "days_remaining": days_left,
    }


@router.delete("/goals/{goal_id}")
def remove_savings_goal(
    goal_id: int,
    db: Session = Depends(get_db),
):
    success = delete_savings_goal(db, goal_id)
    if not success:
        raise HTTPException(404, "Savings goal not found")
    return {"status": "deleted"}


# ============= BILL REMINDERS =============
@router.post("/bills", response_model=BillReminderOut)
def add_bill_reminder(
    payload: BillReminderCreate,
    db: Session = Depends(get_db),
):
    return create_bill_reminder(db, payload)


@router.get("/bills", response_model=list[BillReminderOut])
def list_bill_reminders(db: Session = Depends(get_db)):
    bills = get_bill_reminders(db)
    # Add calculated fields
    result = []
    for bill in bills:
        days_until_due = (bill.due_date - date.today()).days
        is_overdue = days_until_due < 0
        result.append({
            **bill.__dict__,
            "days_until_due": days_until_due,
            "is_overdue": is_overdue,
        })
    return result


@router.patch("/bills/{bill_id}/pay")
def mark_bill_as_paid(
    bill_id: int,
    db: Session = Depends(get_db),
):
    bill = mark_bill_paid(db, bill_id)
    if not bill:
        raise HTTPException(404, "Bill not found")
    return bill


@router.delete("/bills/{bill_id}")
def remove_bill_reminder(
    bill_id: int,
    db: Session = Depends(get_db),
):
    success = delete_bill_reminder(db, bill_id)
    if not success:
        raise HTTPException(404, "Bill not found")
    return {"status": "deleted"}


# ============= EXPENSE FORECASTING =============
@router.post("/forecast/{category}")
def generate_forecast(
    category: str,
    months_back: int = 3,
    db: Session = Depends(get_db),
):
    predicted = calculate_expense_forecast(db, category, months_back)
    if predicted is None:
        raise HTTPException(404, "No historical data for forecast")
    return {"category": category, "predicted_amount": predicted}


@router.get("/forecast", response_model=list[ExpenseForecastOut])
def list_forecasts(month: str = None, db: Session = Depends(get_db)):
    return get_expense_forecasts(db, month)


@router.get("/trends")
def list_trends(months: int = 6, top_n: int = 5, db: Session = Depends(get_db)):
    """Return spending trends for top categories over the given months."""
    return compute_category_trends(db, months=months, top_n=top_n)


# ============= CURRENCY EXCHANGE =============
@router.post("/currency/{from_currency}/{to_currency}/{rate}")
def set_exchange_rate(
    from_currency: str,
    to_currency: str,
    rate: float,
    db: Session = Depends(get_db),
):
    return update_exchange_rate(db, from_currency, to_currency, rate)


@router.get("/currency/{from_currency}/{to_currency}", response_model=CurrencyExchangeOut)
def get_exchange(
    from_currency: str,
    to_currency: str,
    db: Session = Depends(get_db),
):
    exchange = get_exchange_rate(db, from_currency, to_currency)
    if not exchange:
        raise HTTPException(404, "Exchange rate not found")
    return exchange


@router.get("/currency", response_model=list[CurrencyExchangeOut])
def list_exchange_rates(db: Session = Depends(get_db)):
    return get_all_exchange_rates(db)

