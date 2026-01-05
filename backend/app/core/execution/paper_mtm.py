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

    if not intents:
        return []

    for intent in intents:
        ticket = intent.ticket

        # ---- VALIDATION (FAIL FAST) ----
        if not ticket or "legs" not in ticket:
            continue

        lot_size = ticket.get("lot_size", 1)
        lots = ticket.get("lots", 1)
        quantity = lot_size * lots

        symbols = [leg["symbol"] for leg in ticket["legs"]]

        # ---- LIVE LTP ----
        ltp_map = get_ltp(symbols)

        pnl = 0.0

        # ---- MTM PER LEG ----
        for leg in ticket["legs"]:
            symbol = leg["symbol"]
            entry_price = leg.get("price")     # 🔥 STORED PRICE
            current_price = ltp_map.get(symbol)

            if entry_price is None or current_price is None:
                continue

            if leg["side"] == "SELL":
                leg_pnl = (entry_price - current_price) * quantity
            else:  # BUY
                leg_pnl = (current_price - entry_price) * quantity

            pnl += leg_pnl

        # ---- PERSIST ----
        intent.pnl = round(pnl, 2)
        intent.last_mtm_at = now_ist()

    db.commit()