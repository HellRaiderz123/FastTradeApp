import os
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent
from app.core.execution.factory import get_execution_adapter
from app.core.utils.time import now_ist
from app.core.market.ltp import get_ltp
from app.core.execution.mode import get_execution_mode

router = APIRouter(prefix="/paper", tags=["Paper Trading"])

EXECUTION_MODE = os.getenv("EXECUTION_MODE")  # legacy; do not rely on this at runtime


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/positions")
def get_positions(db: Session = Depends(get_db)):
    """Return open positions summary for the terminal badge."""
    intents = (
        db.query(ExecutionIntent)
        .filter(
            ExecutionIntent.status == "EXECUTED",
            ExecutionIntent.closed_at == None,  # noqa: E711
        )
        .all()
    )
    positions = [
        {
            "intent_id": i.intent_id,
            "strategy": i.strategy,
            "underlying": i.underlying,
            "quantity": 1,
            "pnl": float(i.pnl or 0),
        }
        for i in intents
    ]
    return {
        "positions": positions,
        "open_count": len(positions),
        "total_pnl": round(sum(p["pnl"] for p in positions), 2),
    }


@router.post("/mtm/update")
def update_mtm(db: Session = Depends(get_db)):
    execution_mode = get_execution_mode()
    executor = get_execution_adapter(execution_mode)

    intents = (
        db.query(ExecutionIntent)
        .filter(ExecutionIntent.status == "EXECUTED")
        .all()
    )

    results = []

    for intent in intents:
        pnl = executor.mtm(intent)

        intent.pnl = pnl # type: ignore
        intent.last_mtm_at = now_ist() # type: ignore

        results.append(
            {
                "intent_id": intent.intent_id,
                "strategy": intent.strategy,
                "pnl": pnl,
                "last_mtm_at": intent.last_mtm_at,
            }
        )

    db.commit()
    return results

def compute_spread_mtm(intent) -> float:
    ticket = intent.ticket
    symbols = []

    for leg in ticket["legs"]:
        symbols.append(f'{leg["strike"]}{leg["type"]}')

    ltp = get_ltp(symbols)

    cost_to_close = 0.0

    for leg in ticket["legs"]:
        sym = f'{leg["strike"]}{leg["type"]}'
        price = ltp[sym]

        if leg["side"] == "SELL":
            cost_to_close += price
        else:
            cost_to_close -= price

    # 🔥 THE RULE
    return intent.entry_credit - cost_to_close
