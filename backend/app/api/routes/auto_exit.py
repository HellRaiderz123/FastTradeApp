from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.core.exit.auto_exit import run_auto_exit

router = APIRouter(prefix="/exit", tags=["Auto Exit"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/auto")
def auto_exit(db: Session = Depends(get_db)):
    exited = run_auto_exit(db)
    return {
        "exited_intents": exited,
        "count": len(exited),
    }
