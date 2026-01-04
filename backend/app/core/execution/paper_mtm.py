from datetime import datetime
import os
from typing import cast
from app.core.market.ltp import get_ltp
from sqlalchemy.orm import Session

from app.db.models_intent import ExecutionIntent
from app.core.utils.time import now_ist
from app.core.broker.zerodha.client import get_kite_client
from app.core.execution.paper import PaperExecutionAdapter
from app.core.execution.zerodha import ZerodhaExecutionAdapter

EXECUTION_MODE = os.getenv("EXECUTION_MODE")  # later env-based

def calculate_spread_mtm(ticket: dict, entry_credit: float) -> float:
    """
    MTM = entry_credit - current_cost_to_close
    """

    symbols = []
    for leg in ticket["legs"]:
        symbols.append(f'{leg["strike"]}{leg["type"]}')

    ltp = get_ltp(symbols)

    current_cost = 0.0
    for leg in ticket["legs"]:
        sym = f'{leg["strike"]}{leg["type"]}'
        price = ltp[sym]

        if leg["side"] == "SELL":
            current_cost += price
        else:
            current_cost -= price

    current_cost *= ticket["lot_size"] * ticket["lots"]

    return entry_credit - current_cost

def update_paper_mtm(db: Session):
    """
    Update MTM for all EXECUTED trades (paper or zerodha).
    """

    # ✅ Choose adapter ONCE
    if EXECUTION_MODE == "PAPER":
        executor = PaperExecutionAdapter()
    else:
        kite = get_kite_client()
        executor = ZerodhaExecutionAdapter(kite, dry_run=True)

    intents = (
        db.query(ExecutionIntent)
        .filter(
            ExecutionIntent.executed.is_(True),
            ExecutionIntent.status == "EXECUTED",
        )
        .all()
    )

    for intent in intents:
        try:
            pnl = executor.mtm(intent)
        except Exception as e:
            # MTM must NEVER crash system
            print(f"⚠️ MTM failed for intent {intent.intent_id}: {e}")
            continue

        intent.pnl = cast(float, pnl) # type: ignore
        intent.last_mtm_at = now_ist() # type: ignore

    db.commit()