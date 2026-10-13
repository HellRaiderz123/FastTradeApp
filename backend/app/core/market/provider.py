"""
Market data provider abstraction.

Routes historical candle fetches and LTP calls to either Zerodha or INDstocks
based on the CANDLES_SOURCE environment variable.

  CANDLES_SOURCE=ZERODHA    -> KiteConnect (default, existing behaviour)
  CANDLES_SOURCE=INDSTOCKS  -> INDstocks REST API (free, no subscription needed)

All callers (candles.py, ltp.py, spot.py) import from here instead of
importing directly from the Zerodha client.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_ZERODHA_INTERVAL_MAP = {
    "1 Min":  "minute",
    "5 Min":  "5minute",
    "15 Min": "15minute",
    "1 Hour": "60minute",
    "Day":    "day",
    "Week":   "day",   # fetched as daily then aggregated
}


def get_candles_source() -> str:
    return os.getenv("CANDLES_SOURCE", "ZERODHA").upper().strip()


def is_indstocks() -> bool:
    return get_candles_source() == "INDSTOCKS"


# ── Historical candles ─────────────────────────────────────────────────────

def fetch_candles(
    symbol: str,
    interval_label: str,
    from_dt: datetime,
    to_dt: datetime,
) -> List[Dict]:
    """
    Fetch OHLCV candles for a symbol over a date range.

    Returns list of dicts: {date, open, high, low, close, volume}
    interval_label: "1 Min" | "5 Min" | "15 Min" | "1 Hour" | "Day" | "Week"
    """
    if is_indstocks():
        return _fetch_candles_indstocks(symbol, interval_label, from_dt, to_dt)
    return _fetch_candles_zerodha(symbol, interval_label, from_dt, to_dt)


def _fetch_candles_zerodha(
    symbol: str,
    interval_label: str,
    from_dt: datetime,
    to_dt: datetime,
) -> List[Dict]:
    from app.core.broker.zerodha.client import get_kite_client
    from app.core.broker.zerodha.instruments import get_index_token, get_equity_token, INDEX_TOKENS

    kite = get_kite_client()
    sym = symbol.upper().strip()
    token = get_index_token(sym) if sym in INDEX_TOKENS else get_equity_token(sym, exchange="NSE")
    interval = _ZERODHA_INTERVAL_MAP[interval_label]

    candles = kite.historical_data(
        instrument_token=token,
        from_date=from_dt,
        to_date=to_dt,
        interval=interval,
    )
    return [
        {
            "date":   c["date"].replace(tzinfo=None) if hasattr(c["date"], "tzinfo") else c["date"],
            "open":   float(c["open"]),
            "high":   float(c["high"]),
            "low":    float(c["low"]),
            "close":  float(c["close"]),
            "volume": int(c["volume"]),
        }
        for c in candles
    ]


def _fetch_candles_indstocks(
    symbol: str,
    interval_label: str,
    from_dt: datetime,
    to_dt: datetime,
) -> List[Dict]:
    from app.core.broker.indstocks.market_data import fetch_historical, get_scrip_code

    sym = symbol.upper().strip()
    scrip_code = get_scrip_code(sym)
    return fetch_historical(scrip_code, interval_label, from_dt, to_dt)


# ── Live LTP ───────────────────────────────────────────────────────────────

def fetch_ltp(symbols: List[str]) -> Dict[str, float]:
    """
    Fetch last traded price for a list of symbols.
    Returns {symbol: ltp} for symbols that returned data.
    """
    if is_indstocks():
        return _fetch_ltp_indstocks(symbols)
    return _fetch_ltp_zerodha(symbols)


def _fetch_ltp_zerodha(symbols: List[str]) -> Dict[str, float]:
    from app.core.broker.zerodha.client import get_kite_client
    from app.core.broker.zerodha.instruments import get_index_token, INDEX_TOKENS

    kite = get_kite_client()
    normalized: Dict[str, str] = {}
    for sym in symbols:
        sym_upper = sym.upper()
        if sym_upper in INDEX_TOKENS:
            normalized[sym] = str(get_index_token(sym_upper))
        elif ":" in sym:
            normalized[sym] = sym
        else:
            is_option = (
                (sym_upper.endswith("CE") or sym_upper.endswith("PE")) and len(sym) > 10
            ) or sym_upper.endswith("FUT")
            normalized[sym] = f"NFO:{sym}" if is_option else f"NSE:{sym}"

    try:
        data = kite.ltp(list(normalized.values()))
    except Exception as exc:
        logger.warning("Zerodha LTP fetch error: %s", exc)
        return {}

    result: Dict[str, float] = {}
    for original, key in normalized.items():
        info = data.get(key) or data.get(str(key))
        if info and isinstance(info, dict):
            price = float(info.get("last_price") or 0)
            if price > 0:
                result[original] = price
    return result


def _fetch_ltp_indstocks(symbols: List[str]) -> Dict[str, float]:
    from app.core.broker.indstocks.market_data import fetch_ltp_by_symbol
    return fetch_ltp_by_symbol(symbols)


# ── Bulk quotes (scanner-compatible shape) ────────────────────────────────

def get_bulk_quotes(symbols: List[str]) -> Dict[str, Dict]:
    """
    Return quotes keyed by "NSE:SYMBOL" with at least {"last_price": float}.
    Mirrors the shape KiteConnectService.get_bulk_quotes() returns so callers
    need no changes when switching providers.
    """
    if not symbols:
        return {}
    try:
        ltps = fetch_ltp(symbols)
        return {
            f"NSE:{sym}": {"last_price": price}
            for sym, price in ltps.items()
            if price and price > 0
        }
    except Exception as exc:
        logger.warning("get_bulk_quotes failed: %s", exc)
        return {}


# ── Spot price ─────────────────────────────────────────────────────────────

def fetch_spot(underlying: str) -> Optional[float]:
    """
    Fetch live spot price for an index/underlying.
    Returns None if unavailable (caller should fall back to candle close).
    """
    try:
        prices = fetch_ltp([underlying])
        return prices.get(underlying)
    except Exception as exc:
        logger.warning("fetch_spot failed for %s: %s", underlying, exc)
        return None
