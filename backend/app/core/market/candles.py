from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy import and_, text
from app.core.market.provider import fetch_candles
from app.core.broker.zerodha.instruments import INDEX_TOKENS
from app.db.models_candles import Candle1m, Candle5m, Candle15m, Candle1h, CandleDaily, CandleWeekly
from app.db.session import engine
from app.core.utils.time import now_ist

import logging

logger = logging.getLogger("candles")
logger.setLevel(logging.INFO)

_IS_POSTGRES = engine.dialect.name == "postgresql"


def _bulk_upsert(db: Session, model, rows: list[dict]) -> int:
    """Insert rows with ON CONFLICT DO NOTHING. Works for both Postgres and SQLite."""
    if not rows:
        return 0
    if _IS_POSTGRES:
        stmt = pg_insert(model).values(rows).on_conflict_do_nothing()
    else:
        stmt = sqlite_insert(model).values(rows).prefix_with("OR IGNORE")
    result = db.execute(stmt)
    db.commit()
    return result.rowcount if result.rowcount >= 0 else len(rows)

# Zerodha historical data API limits (max days per request)
ZERODHA_MAX_DAYS = {
    "1 Min":  60,    # minute
    "5 Min":  100,   # 5minute
    "15 Min": 200,   # 15minute
    "1 Hour": 365,   # 60minute
    "Day":    2000,  # day
    "Week":   2000,  # aggregated from daily
}

def fetch_15m_candles(db: Session, symbol: str, days: int = 15):
    symbol = symbol.upper().strip()
    to_dt = now_ist()
    from_dt = to_dt - timedelta(days=days)
    candles = fetch_candles(symbol, "15 Min", from_dt, to_dt)
    rows = [
        {"symbol": symbol, "timestamp": c["date"],
         "open": c["open"], "high": c["high"], "low": c["low"],
         "close": c["close"], "volume": c["volume"]}
        for c in candles
    ]
    inserted = _bulk_upsert(db, Candle15m, rows)
    logger.info("15m candles inserted for %s: %d (skipped duplicates)", symbol, inserted)


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


def fetch_daily_candles(db: Session, symbol: str, days: int = 2000):
    """Fetch and store daily candles for a symbol."""
    symbol = symbol.upper().strip()
    to_dt = now_ist()
    from_dt = to_dt - timedelta(days=days)
    candles = fetch_candles(symbol, "Day", from_dt, to_dt)
    candles = sorted(candles, key=lambda c: c["date"])

    is_index = symbol in INDEX_TOKENS
    baseline_close = None
    if not is_index and candles:
        latest_row = (
            db.query(CandleDaily.date, CandleDaily.close)
            .filter(CandleDaily.symbol == symbol)
            .order_by(CandleDaily.date.desc())
            .first()
        )
        if latest_row:
            latest_date = latest_row[0].date() if hasattr(latest_row[0], "date") else latest_row[0]
            first_candle_date = candles[0]["date"].date() if hasattr(candles[0]["date"], "date") else candles[0]["date"]
            if latest_date and abs((latest_date - first_candle_date).days) <= 10:
                baseline_close = float(latest_row[1] or 0)

    rows = []
    skipped_sanity = 0
    for c in candles:
        ts = c["date"].date() if hasattr(c["date"], "date") else c["date"]
        if not is_index and not _is_price_sane(c["close"], baseline_close):
            logger.warning("REJECTED corrupt candle: %s %s close=%.2f vs baseline=%.2f",
                           symbol, ts, c["close"], baseline_close or 0)
            skipped_sanity += 1
            continue
        rows.append({"symbol": symbol, "date": ts,
                     "open": c["open"], "high": c["high"], "low": c["low"],
                     "close": c["close"], "volume": c["volume"]})
        baseline_close = c["close"]

    inserted = _bulk_upsert(db, CandleDaily, rows)
    if skipped_sanity:
        logger.warning("Daily candles for %s: inserted=%d, rejected=%d (price sanity)",
                       symbol, inserted, skipped_sanity)
    else:
        logger.info("Daily candles inserted for %s: %d (skipped duplicates)", symbol, inserted)


# ── Additional timeframe fetchers ──────────────────────────────────────────

def fetch_1m_candles(db: Session, symbol: str, days: int = 60):
    """Fetch and store 1-minute candles for a symbol."""
    symbol = symbol.upper().strip()
    to_dt = now_ist()
    from_dt = to_dt - timedelta(days=min(days, ZERODHA_MAX_DAYS["1 Min"]))
    candles = fetch_candles(symbol, "1 Min", from_dt, to_dt)
    rows = [
        {"symbol": symbol, "timestamp": c["date"],
         "open": c["open"], "high": c["high"], "low": c["low"],
         "close": c["close"], "volume": c["volume"]}
        for c in candles
    ]
    inserted = _bulk_upsert(db, Candle1m, rows)
    logger.info("1m candles inserted for %s: %d (skipped duplicates)", symbol, inserted)


def fetch_5m_candles(db: Session, symbol: str, days: int = 100):
    """Fetch and store 5-minute candles for a symbol."""
    symbol = symbol.upper().strip()
    to_dt = now_ist()
    from_dt = to_dt - timedelta(days=min(days, ZERODHA_MAX_DAYS["5 Min"]))
    candles = fetch_candles(symbol, "5 Min", from_dt, to_dt)
    rows = [
        {"symbol": symbol, "timestamp": c["date"],
         "open": c["open"], "high": c["high"], "low": c["low"],
         "close": c["close"], "volume": c["volume"]}
        for c in candles
    ]
    inserted = _bulk_upsert(db, Candle5m, rows)
    logger.info("5m candles inserted for %s: %d (skipped duplicates)", symbol, inserted)


def fetch_1h_candles(db: Session, symbol: str, days: int = 365):
    """Fetch and store 1-hour candles for a symbol."""
    symbol = symbol.upper().strip()
    to_dt = now_ist()
    from_dt = to_dt - timedelta(days=min(days, ZERODHA_MAX_DAYS["1 Hour"]))
    candles = fetch_candles(symbol, "1 Hour", from_dt, to_dt)
    rows = [
        {"symbol": symbol, "timestamp": c["date"],
         "open": c["open"], "high": c["high"], "low": c["low"],
         "close": c["close"], "volume": c["volume"]}
        for c in candles
    ]
    inserted = _bulk_upsert(db, Candle1h, rows)
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


def aggregate_daily_to_weekly(db: Session, symbol: str):
    """Generate weekly candles by aggregating daily candles in DB.
    Week starts on Monday. Partial weeks (e.g. current week) are included.
    """
    from datetime import timedelta as _td
    symbol = symbol.upper().strip()

    all_daily = (
        db.query(CandleDaily)
        .filter(CandleDaily.symbol == symbol)
        .order_by(CandleDaily.date)
        .all()
    )
    if not all_daily:
        logger.warning("No daily candles for %s — nothing to aggregate to weekly", symbol)
        return

    # Group by ISO week (Monday as week start)
    weekly: dict = {}
    for c in all_daily:
        d = c.date if not hasattr(c.date, "date") else c.date.date()
        week_start = d - _td(days=d.weekday())  # Monday
        if week_start not in weekly:
            weekly[week_start] = []
        weekly[week_start].append(c)

    inserted = 0
    for week_start, bars in sorted(weekly.items()):
        exists = db.query(CandleWeekly.id).filter(
            and_(CandleWeekly.symbol == symbol, CandleWeekly.date == week_start)
        ).first()
        if exists:
            continue
        db.add(CandleWeekly(
            symbol=symbol,
            date=week_start,
            open=bars[0].open,
            high=max(b.high for b in bars),
            low=min(b.low for b in bars),
            close=bars[-1].close,
            volume=sum(b.volume or 0 for b in bars),
        ))
        inserted += 1

    db.commit()
    logger.info("Weekly candles aggregated from daily for %s: %d (skipped existing)", symbol, inserted)


def fetch_weekly_candles(db: Session, symbol: str, days: int = 2000):
    """Fetch daily candles then aggregate to weekly."""
    fetch_daily_candles(db, symbol, days=days)
    aggregate_daily_to_weekly(db, symbol)


TIMEFRAME_FETCHER = {
    "1 Min":  fetch_1m_candles,
    "5 Min":  fetch_5m_candles,
    "15 Min": fetch_15m_candles,
    "1 Hour": fetch_1h_candles,
    "Day":    fetch_daily_candles,
    "Week":   fetch_weekly_candles,
}
