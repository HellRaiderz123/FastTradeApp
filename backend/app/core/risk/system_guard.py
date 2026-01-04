from sqlalchemy.orm import Session
from app.db.models_control import SystemControl


def is_trading_enabled(db: Session) -> bool:
    row = db.query(SystemControl).first()
    return bool(row and row.trading_enabled)
