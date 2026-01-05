from sqlalchemy.orm import Session
from typing import Dict
from app.core.signals.ta_engine import ta_signal_15m
from app.core.signals.ml_engine import ml_signal

def generate_signal(
    db: Session,
    symbol: str,
    use_ml: bool = False,
) -> Dict:
    ta = ta_signal_15m(db, symbol)

    if use_ml:
        ml = ml_signal(symbol)
        if ml["confidence"] > ta["confidence"]:
            return ml

    return ta
