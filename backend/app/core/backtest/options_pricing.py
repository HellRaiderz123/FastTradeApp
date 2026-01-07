from __future__ import annotations

import bisect
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

from app.core.broker.zerodha.client import get_kite_client
from app.core.broker.zerodha.instruments import load_instruments

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CandleSeries:
    times: List[datetime]
    closes: List[float]

    def price_at(self, ts: datetime) -> float:
        """Price at or before ts (forward-fill from last known candle)."""
        if not self.times:
            return 0.0

        idx = bisect.bisect_right(self.times, ts) - 1
        if idx < 0:
            return float(self.closes[0])
        return float(self.closes[idx])


def _series_from_zerodha_candles(candles: List[dict]) -> CandleSeries:
    times: List[datetime] = []
    closes: List[float] = []

    for c in candles or []:
        dt = c.get("date")
        if isinstance(dt, datetime):
            dt = dt.replace(tzinfo=None)
        else:
            continue
        times.append(dt)
        closes.append(float(c.get("close") or 0.0))

    return CandleSeries(times=times, closes=closes)


# Cache: (instrument_token, from_dt, to_dt, interval) -> CandleSeries
_SERIES_CACHE: Dict[Tuple[int, datetime, datetime, str], CandleSeries] = {}


def get_instrument_token_for_tradingsymbol(
    tradingsymbol: str,
    instruments_df: Optional[pd.DataFrame] = None,
) -> int:
    """Resolve an NFO instrument token for a tradingsymbol.

    Important limitation: Zerodha instruments dump generally contains only currently
    listed contracts (expired contracts may be absent). Options backtests therefore
    work best for very recent days / current expiry.
    """
    ts = (tradingsymbol or "").strip().upper()
    if not ts:
        raise ValueError("tradingsymbol is required")

    df = instruments_df if instruments_df is not None else load_instruments()
    if df.empty:
        raise RuntimeError("Zerodha instruments list is empty; cannot resolve tokens")

    row = df.loc[df["tradingsymbol"].astype(str).str.upper() == ts]
    if row.empty:
        raise KeyError(f"tradingsymbol not found in instruments: {ts}")

    tok = row.iloc[0].get("instrument_token")
    if tok is None:
        raise KeyError(f"instrument_token missing for tradingsymbol: {ts}")

    return int(tok)


def fetch_option_series(
    tradingsymbol: str,
    from_dt: datetime,
    to_dt: datetime,
    interval: str = "15minute",
    instruments_df: Optional[pd.DataFrame] = None,
) -> CandleSeries:
    """Fetch historical candle series for an option tradingsymbol."""
    token = get_instrument_token_for_tradingsymbol(tradingsymbol, instruments_df=instruments_df)

    key = (token, from_dt, to_dt, interval)
    cached = _SERIES_CACHE.get(key)
    if cached is not None:
        return cached

    kite = get_kite_client()
    candles = kite.historical_data(
        instrument_token=token,
        from_date=from_dt,
        to_date=to_dt,
        interval=interval,
    )

    series = _series_from_zerodha_candles(candles)
    _SERIES_CACHE[key] = series

    logger.info(
        "Fetched option series: %s token=%s candles=%d",
        tradingsymbol,
        token,
        len(series.times),
    )

    return series
