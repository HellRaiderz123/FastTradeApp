from sqlalchemy.orm import Session
from app.db.models_finance import FinanceTransaction
from app.api.schemas.finance import (
    FinanceTransactionCreate,
    FinanceTransactionUpdate,
)


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
