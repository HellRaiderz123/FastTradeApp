from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.core.broker.zerodha.client import get_kite_client
from app.core.broker.zerodha.instruments import get_index_token, get_equity_token, INDEX_TOKENS
from app.db.models_candles import Candle1m, Candle5m, Candle15m, Candle1h, CandleDaily
from app.core.utils.time import now_ist

import logging

logger = logging.getLogger("candles")
logger.setLevel(logging.INFO)

from sqlalchemy import and_

# Zerodha historical data API limits (max days per request)
ZERODHA_MAX_DAYS = {
    "1 Min":  60,    # minute
    "5 Min":  100,   # 5minute
    "15 Min": 200,   # 15minute
    "1 Hour": 365,   # 60minute
    "Day":    2000,  # day
}

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


def _get_recent_close(db: Session, symbol: str) -> float | None:
    """Get the most recent close price for a symbol to use as sanity baseline."""
    row = (
        db.query(CandleDaily.close)
        .filter(CandleDaily.symbol == symbol)
        .order_by(CandleDaily.date.desc())
        .first()
    )
    return float(row[0]) if row else None


def _is_price_sane(close: float, baseline: float | None, threshold: float = 0.50) -> bool:
    """Reject candle if close deviates more than `threshold` (50%) from baseline.
    This catches corrupted data like index values inserted into stock rows.
    """
    if baseline is None or baseline <= 0:
        return True  # no baseline yet, accept
    ratio = close / baseline
    return (1 - threshold) <= ratio <= (1 + threshold)


def fetch_daily_candles(db: Session, symbol: str, days: int = 400):
    """Fetch and store daily candles for a symbol."""
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
        interval="day",
    )

    # Get baseline price for sanity checking (skip for index symbols)
    is_index = symbol in INDEX_TOKENS
    baseline_close = None if is_index else _get_recent_close(db, symbol)

    inserted = 0
    skipped_sanity = 0

    for c in candles:
        ts = c["date"].date() if hasattr(c["date"], "date") else c["date"]

        exists = db.query(CandleDaily.id).filter(
            and_(
                CandleDaily.symbol == symbol,
                CandleDaily.date == ts,
            )
        ).first()

        if exists:
            continue

        # Sanity check: reject if price deviates >50% from recent close
        if not is_index and not _is_price_sane(c["close"], baseline_close):
            logger.warning(
                "REJECTED corrupt candle: %s %s close=%.2f vs baseline=%.2f",
                symbol, ts, c["close"], baseline_close or 0,
            )
            skipped_sanity += 1
            continue

        db.add(
            CandleDaily(
                symbol=symbol,
                date=ts,
                open=c["open"],
                high=c["high"],
                low=c["low"],
                close=c["close"],
                volume=c["volume"],
            )
        )
        inserted += 1
        # Update baseline for subsequent candles in this batch
        baseline_close = c["close"]

    db.commit()

    if skipped_sanity:
        logger.warning("Daily candles for %s: inserted=%d, rejected=%d (price sanity)",
                       symbol, inserted, skipped_sanity)
    else:
        logger.info("Daily candles inserted: %d (skipped duplicates)", inserted)


# ── Additional timeframe fetchers ──────────────────────────────────────────

def fetch_1m_candles(db: Session, symbol: str, days: int = 60):
    """Fetch and store 1-minute candles for a symbol.
    Zerodha limit: up to 60 days per request.
    """
    symbol = symbol.upper().strip()

    kite = get_kite_client()
    if symbol in INDEX_TOKENS:
        token = get_index_token(symbol)
    else:
        token = get_equity_token(symbol, exchange="NSE")

    to_dt = now_ist()
    from_dt = to_dt - timedelta(days=min(days, ZERODHA_MAX_DAYS["1 Min"]))

    candles = kite.historical_data(
        instrument_token=token,
        from_date=from_dt,
        to_date=to_dt,
        interval="minute",
    )

    inserted = 0
    for c in candles:
        ts = c["date"].replace(tzinfo=None)
        exists = db.query(Candle1m.id).filter(
            and_(Candle1m.symbol == symbol, Candle1m.timestamp == ts)
        ).first()
        if exists:
            continue
        db.add(Candle1m(
            symbol=symbol, timestamp=ts,
            open=c["open"], high=c["high"], low=c["low"],
            close=c["close"], volume=c["volume"],
        ))
        inserted += 1

    db.commit()
    logger.info("1m candles inserted for %s: %d (skipped duplicates)", symbol, inserted)


def fetch_5m_candles(db: Session, symbol: str, days: int = 100):
    """Fetch and store 5-minute candles for a symbol.
    Zerodha limit: up to 100 days per request.
    """
    symbol = symbol.upper().strip()

    kite = get_kite_client()
    if symbol in INDEX_TOKENS:
        token = get_index_token(symbol)
    else:
        token = get_equity_token(symbol, exchange="NSE")

    to_dt = now_ist()
    from_dt = to_dt - timedelta(days=min(days, ZERODHA_MAX_DAYS["5 Min"]))

    candles = kite.historical_data(
        instrument_token=token,
        from_date=from_dt,
        to_date=to_dt,
        interval="5minute",
    )

    inserted = 0
    for c in candles:
        ts = c["date"].replace(tzinfo=None)
        exists = db.query(Candle5m.id).filter(
            and_(Candle5m.symbol == symbol, Candle5m.timestamp == ts)
        ).first()
        if exists:
            continue
        db.add(Candle5m(
            symbol=symbol, timestamp=ts,
            open=c["open"], high=c["high"], low=c["low"],
            close=c["close"], volume=c["volume"],
        ))
        inserted += 1

    db.commit()
    logger.info("5m candles inserted for %s: %d (skipped duplicates)", symbol, inserted)


def fetch_1h_candles(db: Session, symbol: str, days: int = 365):
    """Fetch and store 1-hour candles for a symbol.
    Zerodha limit: up to 365 days per request.
    """
    symbol = symbol.upper().strip()

    kite = get_kite_client()
    if symbol in INDEX_TOKENS:
        token = get_index_token(symbol)
    else:
        token = get_equity_token(symbol, exchange="NSE")

    to_dt = now_ist()
    from_dt = to_dt - timedelta(days=min(days, ZERODHA_MAX_DAYS["1 Hour"]))

    candles = kite.historical_data(
        instrument_token=token,
        from_date=from_dt,
        to_date=to_dt,
        interval="60minute",
    )

    inserted = 0
    for c in candles:
        ts = c["date"].replace(tzinfo=None)
        exists = db.query(Candle1h.id).filter(
            and_(Candle1h.symbol == symbol, Candle1h.timestamp == ts)
        ).first()
        if exists:
            continue
        db.add(Candle1h(
            symbol=symbol, timestamp=ts,
            open=c["open"], high=c["high"], low=c["low"],
            close=c["close"], volume=c["volume"],
        ))
        inserted += 1

    db.commit()
    logger.info("1h candles inserted for %s: %d (skipped duplicates)", symbol, inserted)


# ── Aggregation: generate 1h candles from existing 15m candles ─────────────

def aggregate_15m_to_1h(db: Session, symbol: str):
    """Generate 1-hour candles by aggregating existing 15m candles in DB.
    Useful when 1h Zerodha fetch is unavailable — uses already-stored 15m data.
    """
    symbol = symbol.upper().strip()
    from sqlalchemy import func

    all_15m = (
        db.query(Candle15m)
        .filter(Candle15m.symbol == symbol)
        .order_by(Candle15m.timestamp)
        .all()
    )
    if not all_15m:
        logger.warning("No 15m candles for %s — nothing to aggregate", symbol)
        return

    # Group by hour
    hourly: dict = {}
    for c in all_15m:
        hour_key = c.timestamp.replace(minute=0, second=0, microsecond=0)
        if hour_key not in hourly:
            hourly[hour_key] = []
        hourly[hour_key].append(c)

    inserted = 0
    for hour_ts, bars in sorted(hourly.items()):
        if len(bars) < 2:
            continue  # need at least 2 bars for a valid hourly candle

        exists = db.query(Candle1h.id).filter(
            and_(Candle1h.symbol == symbol, Candle1h.timestamp == hour_ts)
        ).first()
        if exists:
            continue

        db.add(Candle1h(
            symbol=symbol,
            timestamp=hour_ts,
            open=bars[0].open,
            high=max(b.high for b in bars),
            low=min(b.low for b in bars),
            close=bars[-1].close,
            volume=sum(b.volume or 0 for b in bars),
        ))
        inserted += 1

    db.commit()
    logger.info("1h candles aggregated from 15m for %s: %d (skipped existing)", symbol, inserted)


# ── Timeframe fetcher map (for generic backfill) ──────────────────────────

TIMEFRAME_FETCHER = {
    "1 Min":  fetch_1m_candles,
    "5 Min":  fetch_5m_candles,
    "15 Min": fetch_15m_candles,
    "1 Hour": fetch_1h_candles,
    "Day":    fetch_daily_candles,
}
