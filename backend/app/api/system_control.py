from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.system_control_repo import get_or_create_system_control

router = APIRouter(prefix="/system", tags=["System Control"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/enable")
def enable_trading(db: Session = Depends(get_db)):
    sc = get_or_create_system_control(db)
    sc.trading_enabled = True
    db.commit()

    return {"trading_enabled": True}

@router.post("/disable")
def disable_trading(db: Session = Depends(get_db)):
    sc = get_or_create_system_control(db)
    sc.trading_enabled = False
    db.commit()

    return {"trading_enabled": False}

@router.get("/status")
def system_status(db: Session = Depends(get_db)):
    sc = get_or_create_system_control(db)
    return {
        "trading_enabled": sc.trading_enabled
    }
