from datetime import datetime, date
import os
from typing import cast
from app.core.market.ltp import get_ltp
from sqlalchemy.orm import Session

from app.db.models_intent import ExecutionIntent
from app.core.execution.base import get_ticket
from app.core.utils.time import now_ist
from app.core.broker.zerodha_symbols import build_zerodha_option_symbol

EXECUTION_MODE = os.getenv("EXECUTION_MODE")  # legacy; do not rely on this at runtime

def calculate_spread_mtm(
    ticket: dict,
    entry_credit: float,
    underlying: str = "NIFTY",
    expiry: date | None = None,
) -> float:
    """
    MTM = entry_credit - current_cost_to_close

    FIX: Previously built symbols as f'{strike}{type}' (e.g. "26000CE") which is
    not a valid Zerodha symbol. get_ltp() expects full NSE symbols like
    "NIFTY2601026000CE". All MTM values were silently 0 or wrong.

    Now uses build_zerodha_option_symbol() — same builder used by the execution
    adapter — so LTP lookups return real prices.
    """
    symbols = []
    sym_map = {}  # maps leg index → full symbol

    for i, leg in enumerate(ticket["legs"]):
        # Use pre-stored symbol if available (set during execution)
        sym = leg.get("symbol")
        if not sym and expiry is not None:
            sym = build_zerodha_option_symbol(
                underlying=underlying,
                expiry=expiry,
                strike=int(leg["strike"]),
                option_type=str(leg["type"]),
            )
        if sym:
            symbols.append(sym)
            sym_map[i] = sym

    if not symbols:
        return 0.0

    ltp = get_ltp(symbols)

    current_cost = 0.0
    for i, leg in enumerate(ticket["legs"]):
        sym = sym_map.get(i)
        if not sym:
            continue
        price = ltp.get(sym)
        if price is None:
            continue

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
        ticket = get_ticket(intent)

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