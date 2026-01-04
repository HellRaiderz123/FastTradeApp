from sqlalchemy.orm import Session
from app.db.models_control import SystemControl

def get_or_create_system_control(db: Session) -> SystemControl:
    sc = db.query(SystemControl).first()

    if sc is None:
        sc = SystemControl(trading_enabled=True)
        db.add(sc)
        db.commit()
        db.refresh(sc)

    return sc