from sqlalchemy.orm import Session
from app.db.models_intent import ExecutionIntent


def get_intent_by_id(db: Session, intent_id: str):
    return (
        db.query(ExecutionIntent)
        .filter(ExecutionIntent.intent_id == intent_id)
        .first()
    )
