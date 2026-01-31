from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
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
)
from app.api.schemas.finance import (
    FinanceTransactionCreate,
    FinanceTransactionUpdate,
    FinanceTransactionOut,
)

router = APIRouter(prefix="/finance", tags=["Finance"])


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

