"""
INDstocks market data client.
Docs: https://api-docs.indstocks.com/

Key facts from official docs:
  - Auth header: Authorization: <access_token>  (raw token, no "Bearer" prefix)
  - Scrip-code format: SEGMENT_SECURITYID  e.g. NSE_2885, NFO_51011
  - LTP endpoint: GET /market/quotes/ltp  -> data[scrip_code]["live_price"]
  - Full quote:   GET /market/quotes/full -> data[scrip_code]["live_price"]
  - Historical:   GET /market/historical/{interval}
      - start_time / end_time: epoch milliseconds
      - candle ts: epoch seconds
      - max 5 scrip-codes per call
  - Rate limits: Data APIs 5 req/sec, 100k/day
  - WebSocket price feed: wss://ws-prices.indstocks.com/api/v1/ws/prices
      - instrument format: SEGMENT:TOKEN  e.g. NSE:2885  (colon, not underscore)
"""

import csv
import io
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.indstocks.com"

# interval_label -> (api_interval_value, max_days_per_call)
INDSTOCKS_INTERVALS: Dict[str, tuple] = {
    "1 Min":  ("1minute",  7),
    "5 Min":  ("5minute",  7),
    "15 Min": ("15minute", 7),
    "1 Hour": ("60minute", 15),
    "Day":    ("1day",     365),
    "Week":   ("1week",    365),
}


def _access_token() -> str:
    token = os.getenv("INDMONEY_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("INDMONEY_ACCESS_TOKEN is not set in .env")
    return token


def _headers() -> Dict[str, str]:
    # Raw token in Authorization header — no "Bearer" prefix per docs
    return {"Authorization": _access_token()}


def _to_ms(dt: datetime) -> int:
    """datetime -> epoch milliseconds (required by historical API)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _from_ts_seconds(ts: int) -> datetime:
    """Candle ts (epoch seconds) -> naive UTC datetime."""
    return datetime.utcfromtimestamp(ts)


# ── Instruments cache ──────────────────────────────────────────────────────
# Maps TRADING_SYMBOL -> scrip-code (e.g. "RELIANCE" -> "NSE_2885")

_sym_cache: Dict[str, str] = {}
_cache_loaded_at: float = 0.0
_CACHE_TTL = 900  # 15 minutes


def _instruments_cache() -> Dict[str, str]:
    global _sym_cache, _cache_loaded_at
    if _sym_cache and (time.time() - _cache_loaded_at) < _CACHE_TTL:
        return _sym_cache
    _refresh_instruments_cache()
    return _sym_cache


def _refresh_instruments_cache() -> None:
    """
    Fetch instruments CSV for equity, fno, and index sources.

    CSV columns per docs:
      equity/fno: EXCH, SEGMENT, SECURITY_ID, TRADING_SYMBOL, ...
      index:      EXCH, SEGMENT (contains index name), SECURITY_ID  (3 cols only)
    """
    global _sym_cache, _cache_loaded_at
    merged: Dict[str, str] = {}

    for source in ("equity", "fno", "index"):
        try:
            resp = requests.get(
                f"{BASE_URL}/market/instruments",
                params={"source": source},
                headers=_headers(),
                timeout=15,
            )
            resp.raise_for_status()
            reader = csv.DictReader(io.StringIO(resp.text))
            for row in reader:
                if source == "index":
                    # index CSV: EXCH, SEGMENT (=index name), SECURITY_ID
                    exch = (row.get("EXCH") or "NSE").strip().upper()
                    sid = (row.get("SECURITY_ID") or "").strip()
                    # Use the index name (SEGMENT column) as the symbol key
                    sym = (row.get("SEGMENT") or "").strip().upper()
                    if sym and sid:
                        merged[sym] = f"{exch}_{sid}"
                else:
                    exch = (row.get("EXCH") or "NSE").strip().upper()
                    sid = (row.get("SECURITY_ID") or "").strip()
                    sym = (row.get("TRADING_SYMBOL") or "").strip().upper()
                    if sym and sid:
                        merged[sym] = f"{exch}_{sid}"
        except Exception as exc:
            logger.warning("INDstocks instruments fetch failed source=%s: %s", source, exc)

    if merged:
        _sym_cache.update(merged)
        _cache_loaded_at = time.time()
        logger.info("INDstocks instruments cache: %d symbols", len(_sym_cache))


# Common index aliases that callers use (FastTrade uses these names)
_INDEX_ALIASES: Dict[str, str] = {
    "NIFTY":     "NIFTY 50",
    "BANKNIFTY": "NIFTY BANK",
    "FINNIFTY":  "NIFTY FIN SERVICE",
    "NIFTYVIX":  "INDIA VIX",
}


def get_scrip_code(symbol: str) -> str:
    """
    Resolve a plain symbol to an INDstocks scrip-code (e.g. NSE_2885).

    Tries:
      1. Direct lookup in instruments cache
      2. Index alias lookup (NIFTY -> NIFTY 50, etc.)
    """
    sym = symbol.upper().strip()
    cache = _instruments_cache()

    scrip = cache.get(sym)
    if scrip:
        return scrip

    # Try alias
    alias = _INDEX_ALIASES.get(sym)
    if alias:
        scrip = cache.get(alias.upper())
        if scrip:
            return scrip

    raise KeyError(
        f"INDstocks scrip-code not found for '{symbol}'. "
        "Ensure INDMONEY_ACCESS_TOKEN is set and instruments are loaded."
    )


def get_ws_instrument(symbol: str) -> str:
    """
    Return the WebSocket instrument token for a symbol.
    WebSocket format is SEGMENT:SECURITY_ID  (colon, not underscore).
    e.g. scrip-code NSE_2885 -> WS token NSE:2885
    """
    scrip = get_scrip_code(symbol)  # e.g. NSE_2885
    return scrip.replace("_", ":", 1)


# ── Historical candles ─────────────────────────────────────────────────────

def fetch_historical(
    scrip_code: str,
    interval_label: str,
    from_dt: datetime,
    to_dt: datetime,
) -> List[Dict]:
    """
    Fetch OHLCV candles from INDstocks for a single instrument.

    Paginates automatically across the per-call window limit.
    Returns list of dicts: {date, open, high, low, close, volume}
    """
    if interval_label not in INDSTOCKS_INTERVALS:
        raise ValueError(f"Unsupported interval: {interval_label}. Use one of {list(INDSTOCKS_INTERVALS)}")

    api_interval, max_days = INDSTOCKS_INTERVALS[interval_label]
    window = timedelta(days=max_days)
    all_candles: List[Dict] = []
    cursor = from_dt

    while cursor < to_dt:
        end = min(cursor + window, to_dt)
        try:
            resp = requests.get(
                f"{BASE_URL}/market/historical/{api_interval}",
                params={
                    "scrip-codes": scrip_code,
                    "start_time": _to_ms(cursor),
                    "end_time": _to_ms(end),
                },
                headers=_headers(),
                timeout=15,
            )
            resp.raise_for_status()
            body = resp.json()

            if not body.get("success"):
                logger.warning(
                    "INDstocks historical success=false for %s %s: %s",
                    scrip_code, api_interval, body
                )
                break

            candles_raw = (
                (body.get("data") or {})
                .get(scrip_code, {})
                .get("candles") or []
            )
            for c in candles_raw:
                all_candles.append({
                    "date":   _from_ts_seconds(c["ts"]),
                    "open":   float(c["o"]),
                    "high":   float(c["h"]),
                    "low":    float(c["l"]),
                    "close":  float(c["c"]),
                    "volume": int(c["v"]),
                })
        except Exception as exc:
            logger.warning(
                "INDstocks historical fetch error (%s %s): %s",
                scrip_code, api_interval, exc,
            )
            break

        cursor = end

    return all_candles


# ── Live LTP ───────────────────────────────────────────────────────────────

def fetch_ltp(scrip_codes: List[str]) -> Dict[str, float]:
    """
    Fetch last traded price for a list of scrip-codes.

    Per docs: GET /market/quotes/ltp
    Response: {"status": "success", "data": {"NSE_3045": {"live_price": 792.5}}}

    Returns {scrip_code: ltp}.
    """
    if not scrip_codes:
        return {}

    result: Dict[str, float] = {}
    # API accepts up to 1000 per call per docs; batch at 50 to stay safe
    for i in range(0, len(scrip_codes), 50):
        batch = scrip_codes[i: i + 50]
        try:
            resp = requests.get(
                f"{BASE_URL}/market/quotes/ltp",
                params={"scrip-codes": ",".join(batch)},
                headers=_headers(),
                timeout=10,
            )
            resp.raise_for_status()
            body = resp.json()
            data = body.get("data") or {}
            for code, info in data.items():
                # Docs confirm the field is "live_price"
                ltp = info.get("live_price")
                if ltp is not None:
                    result[code] = float(ltp)
        except Exception as exc:
            logger.warning("INDstocks LTP fetch error: %s", exc)

    return result


def fetch_ltp_by_symbol(symbols: List[str]) -> Dict[str, float]:
    """
    Convenience: resolve symbols -> scrip-codes -> LTP -> return keyed by original symbol.
    """
    sym_to_scrip: Dict[str, str] = {}
    for sym in symbols:
        try:
            sym_to_scrip[sym] = get_scrip_code(sym)
        except KeyError:
            logger.warning("INDstocks: no scrip-code for '%s', skipping LTP", sym)

    if not sym_to_scrip:
        return {}

    scrip_to_ltp = fetch_ltp(list(sym_to_scrip.values()))
    return {
        sym: scrip_to_ltp[scrip]
        for sym, scrip in sym_to_scrip.items()
        if scrip in scrip_to_ltp
    }
