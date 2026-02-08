from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.core.broker.zerodha.client import get_kite_client
from app.core.broker.zerodha.instruments import get_index_token, get_equity_token, INDEX_TOKENS
from app.db.models_candles import Candle15m
from app.core.utils.time import now_ist

import logging

logger = logging.getLogger("candles")
logger.setLevel(logging.INFO)

from sqlalchemy import and_

def fetch_15m_candles(db: Session, symbol: str, days: int = 15):
    symbol = symbol.upper().strip()

    kite = get_kite_client()
    if symbol in INDEX_TOKENS:
        token = get_index_token(symbol)
    else:
        token = get_equity_token(symbol, exchange="NSE")

    to_dt = now_ist()
    from_dt = to_dt - timedelta(days=days)

    candles = kite.historical_data(
        instrument_token=token,
        from_date=from_dt,
        to_date=to_dt,
        interval="15minute",
    )

    inserted = 0

    for c in candles:
        ts = c["date"].replace(tzinfo=None)

        exists = db.query(Candle15m.id).filter(
            and_(
                Candle15m.symbol == symbol,
                Candle15m.timestamp == ts,
            )
        ).first()

        if exists:
            continue

        db.add(
            Candle15m(
                symbol=symbol,
                timestamp=ts,
                open=c["open"],
                high=c["high"],
                low=c["low"],
                close=c["close"],
                volume=c["volume"],
            )
        )
        inserted += 1

    db.commit()

    logger.info("Candles inserted: %d (skipped duplicates)", inserted)
