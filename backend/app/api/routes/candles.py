from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models_candles import Candle15m

router = APIRouter(prefix="/candles", tags=["Candles"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/15m/{symbol}")
def get_candles(symbol: str, db: Session = Depends(get_db)):
    return (
        db.query(Candle15m)
        .filter(Candle15m.symbol == symbol)
        .order_by(Candle15m.timestamp.desc())
        .limit(50)
        .all()
    )
