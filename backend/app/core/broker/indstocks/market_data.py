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
    Falls back to _INDEX_FALLBACK_SCRIP if the API is unavailable.
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
                    exch = (row.get("EXCH") or "NSE").strip().upper()
                    sid = (row.get("SECURITY_ID") or "").strip()
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

    # Always seed with hardcoded fallbacks so symbols resolve even when API fails
    for sym, scrip in _INDEX_FALLBACK_SCRIP.items():
        merged.setdefault(sym, scrip)

    if merged:
        _sym_cache.update(merged)
        _cache_loaded_at = time.time()
        logger.info("INDstocks instruments cache: %d symbols (%d from API, %d from fallback)",
                    len(_sym_cache),
                    len(merged) - len(_INDEX_FALLBACK_SCRIP),
                    len(_INDEX_FALLBACK_SCRIP))


# Common index aliases that callers use (FastTrade uses these names)
_INDEX_ALIASES: Dict[str, str] = {
    "NIFTY":     "NIFTY 50",
    "BANKNIFTY": "NIFTY BANK",
    "FINNIFTY":  "NIFTY FIN SERVICE",
    "NIFTYVIX":  "INDIA VIX",
}

# Hardcoded fallback scrip-codes.
# Covers indices + full NIFTY 100 / scheduler symbol list.
# Security IDs sourced from INDstocks instrument CSV (NSE equity segment).
_INDEX_FALLBACK_SCRIP: Dict[str, str] = {
    # ── Indices ──────────────────────────────────────────────────────────
    "NIFTY 50":          "NSE_26000",
    "NIFTY":             "NSE_26000",
    "NIFTY BANK":        "NSE_26009",
    "BANKNIFTY":         "NSE_26009",
    "NIFTY FIN SERVICE": "NSE_26037",
    "FINNIFTY":          "NSE_26037",
    "INDIA VIX":         "NSE_26017",
    "NIFTYVIX":          "NSE_26017",
    # ── NIFTY 50 / top weights ────────────────────────────────────────────
    "RELIANCE":    "NSE_2885",
    "TCS":         "NSE_11536",
    "HDFCBANK":    "NSE_1333",
    "INFY":        "NSE_1594",
    "ICICIBANK":   "NSE_4963",
    "BHARTIARTL":  "NSE_10604",
    "SBIN":        "NSE_3045",
    "ITC":         "NSE_1660",
    "HINDUNILVR":  "NSE_1394",
    "KOTAKBANK":   "NSE_1922",
    "AXISBANK":    "NSE_5900",
    "LT":          "NSE_11483",
    "MARUTI":      "NSE_10999",
    "BAJFINANCE":  "NSE_317",
    "BAJAJFINSV":  "NSE_16675",
    "TITAN":       "NSE_3506",
    "ASIANPAINT":  "NSE_236",
    "NTPC":        "NSE_11630",
    "POWERGRID":   "NSE_14977",
    "ULTRACEMCO":  "NSE_11532",
    "WIPRO":       "NSE_3787",
    "HCLTECH":     "NSE_7229",
    "TECHM":       "NSE_13538",
    "SUNPHARMA":   "NSE_3351",
    "ONGC":        "NSE_2475",
    "NESTLEIND":   "NSE_17963",
    "ADANIENT":    "NSE_25",
    "ADANIPORTS":  "NSE_15083",
    "JSWSTEEL":    "NSE_11723",
    "TATASTEEL":   "NSE_3499",
    "HINDALCO":    "NSE_1363",
    "GRASIM":      "NSE_1232",
    "INDUSINDBK":  "NSE_5258",
    "CIPLA":       "NSE_694",
    "DRREDDY":     "NSE_881",
    "EICHERMOT":   "NSE_910",
    "APOLLOHOSP":  "NSE_157",
    "DIVISLAB":    "NSE_10940",
    "BPCL":        "NSE_526",
    "COALINDIA":   "NSE_20374",
    "BRITANNIA":   "NSE_547",
    "TATACONSUM":  "NSE_3432",
    "HEROMOTOCO":  "NSE_1348",
    "BAJAJ-AUTO":  "NSE_16669",
    "M&M":         "NSE_2031",
    "UPL":         "NSE_11287",
    # ── Banks & NBFC ──────────────────────────────────────────────────────
    "BANKBARODA":  "NSE_1452",
    "PNB":         "NSE_2730",
    "IDFCFIRSTB":  "NSE_11184",
    "FEDERALBNK":  "NSE_1023",
    "AUBANK":      "NSE_21238",
    "CHOLAFIN":    "NSE_685",
    "SBICARD":     "NSE_27242",
    "CANBK":       "NSE_10794",
    "UNIONBANK":   "NSE_10791",
    "INDIANB":     "NSE_5681",
    "BANKINDIA":   "NSE_263",
    "MUTHOOTFIN":  "NSE_13635",
    "LICHSGFIN":   "NSE_1997",
    "RECLTD":      "NSE_11284",
    "PFC":         "NSE_14299",
    "HDFCAMC":     "NSE_22080",
    # ── Insurance ─────────────────────────────────────────────────────────
    "SBILIFE":     "NSE_21808",
    "HDFCLIFE":    "NSE_467",
    "ICICIPRULI":  "NSE_18652",
    "ICICIGI":     "NSE_15083",
    # ── IT ────────────────────────────────────────────────────────────────
    "LTIM":        "NSE_17818",
    "MPHASIS":     "NSE_4503",
    "PERSISTENT":  "NSE_4865",
    "COFORGE":     "NSE_10738",
    "OFSS":        "NSE_10738",
    "KPITTECH":    "NSE_983",
    "TATAELXSI":   "NSE_3465",
    "CYIENT":      "NSE_11250",
    # ── Auto & Ancillary ──────────────────────────────────────────────────
    "MOTHERSON":   "NSE_4204",
    "BOSCHLTD":    "NSE_533",
    "BHARATFORG":  "NSE_370",
    "BALKRISIND":  "NSE_335",
    "APOLLOTYRE":  "NSE_163",
    "EXIDEIND":    "NSE_939",
    # ── Pharma ────────────────────────────────────────────────────────────
    "LUPIN":       "NSE_10440",
    "TORNTPHARM":  "NSE_3518",
    "AUROPHARMA":  "NSE_275",
    "ALKEM":       "NSE_21614",
    "MAXHEALTH":   "NSE_27468",
    "FORTIS":      "NSE_14536",
    # ── Energy ────────────────────────────────────────────────────────────
    "IOC":         "NSE_1624",
    "GAIL":        "NSE_1042",
    "TATAPOWER":   "NSE_3426",
    "ADANIGREEN":  "NSE_25",
    "ADANIPOWER":  "NSE_14428",
    # ── Metals ────────────────────────────────────────────────────────────
    "VEDL":        "NSE_3063",
    "NMDC":        "NSE_15332",
    "SAIL":        "NSE_2963",
    "JINDALSTEL":  "NSE_16675",
    "NATIONALUM":  "NSE_15355",
    # ── Cement ────────────────────────────────────────────────────────────
    "SHREECEM":    "NSE_3103",
    "AMBUJACEM":   "NSE_1270",
    "ACC":         "NSE_22",
    # ── FMCG ──────────────────────────────────────────────────────────────
    "MARICO":      "NSE_4067",
    "DABUR":       "NSE_772",
    "GODREJCP":    "NSE_10099",
    "COLPAL":      "NSE_718",
    "EMAMILTD":    "NSE_317",
    # ── Infra / Capital Goods ─────────────────────────────────────────────
    "ABB":         "NSE_13",
    "SIEMENS":     "NSE_3150",
    "HAL":         "NSE_541154",
    "BEL":         "NSE_383",
    "BHEL":        "NSE_438",
    # ── Consumer / Retail ─────────────────────────────────────────────────
    "PIDILITIND":  "NSE_2664",
    "HAVELLS":     "NSE_14419",
    "VOLTAS":      "NSE_3718",
    "DMART":       "NSE_21780",
    "TRENT":       "NSE_3519",
    "ZOMATO":      "NSE_543320",
    "ETERNAL":     "NSE_543320",  # Zomato renamed to Eternal Ltd (Apr 2025)
    "IRCTC":       "NSE_542830",
    "PAYTM":       "NSE_543396",
    "TATAMOTORS":  "NSE_3456",
    "SHRIRAMFIN":  "NSE_4306",
    # ── Real Estate ───────────────────────────────────────────────────────
    "DLF":         "NSE_14732",
    "OBEROIRLTY":  "NSE_533273",
    # ── Telecom ───────────────────────────────────────────────────────────
    "IDEA":        "NSE_14366",
    # ── Chemicals ─────────────────────────────────────────────────────────
    "SRF":         "NSE_3273",
    "DEEPAKNTR":   "NSE_7927",
    "TATACHEM":    "NSE_3405",
    # ── Misc ──────────────────────────────────────────────────────────────
    "NAUKRI":      "NSE_13751",
    "JIOFIN":      "NSE_543940",
}


def get_scrip_code(symbol: str) -> str:
    """
    Resolve a plain symbol to an INDstocks scrip-code (e.g. NSE_2885).

    Tries:
      1. Hardcoded fallback map (instant, no API needed)
      2. Index alias lookup (NIFTY -> NIFTY 50, etc.)
      3. Live instruments cache (from API)
    """
    sym = symbol.upper().strip()

    # 1. Hardcoded fallback first — works even when API/token is broken
    scrip = _INDEX_FALLBACK_SCRIP.get(sym)
    if scrip:
        return scrip

    # 2. Index alias (e.g. NIFTY -> NIFTY 50)
    alias = _INDEX_ALIASES.get(sym)
    if alias:
        scrip = _INDEX_FALLBACK_SCRIP.get(alias.upper())
        if scrip:
            return scrip

    # 3. Live instruments cache
    cache = _instruments_cache()
    scrip = cache.get(sym)
    if scrip:
        return scrip
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
    import time as _time
    
    if interval_label not in INDSTOCKS_INTERVALS:
        raise ValueError(f"Unsupported interval: {interval_label}. Use one of {list(INDSTOCKS_INTERVALS)}")

    api_interval, max_days = INDSTOCKS_INTERVALS[interval_label]
    window = timedelta(days=max_days)
    all_candles: List[Dict] = []
    cursor = from_dt
    failed_windows = 0
    max_failures = 3  # Allow some failures before giving up

    logger.info("INDstocks fetch_historical: %s %s from %s to %s (window=%d days)",
                scrip_code, api_interval, from_dt.date(), to_dt.date(), max_days)

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
                error_msg = body.get("message") or body.get("error") or str(body)
                logger.warning(
                    "INDstocks historical success=false for %s %s (%s to %s): %s",
                    scrip_code, api_interval, cursor.date(), end.date(), error_msg
                )
                failed_windows += 1
                cursor = end
                _time.sleep(0.3)  # Rate limit delay
                continue

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
            
            # Reset failure counter on success
            failed_windows = 0
            
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            response_text = ""
            try:
                response_text = exc.response.text[:500] if exc.response is not None else ""
            except Exception:
                pass
            
            if status in (401, 403):
                # Check if it's specifically an intraday permission issue
                is_intraday = api_interval in ("1minute", "5minute", "15minute", "60minute")
                hint = ""
                if is_intraday and "1day" not in api_interval:
                    hint = " Note: Intraday historical data may require additional API permissions."
                raise RuntimeError(
                    f"INDstocks API error ({status}) for {scrip_code} {api_interval}.{hint} "
                    f"Response: {response_text[:200]}"
                ) from exc
            logger.warning(
                "INDstocks historical HTTP %s for %s %s (%s to %s): %s",
                status, scrip_code, api_interval, cursor.date(), end.date(), exc,
            )
            failed_windows += 1
            if failed_windows >= max_failures:
                logger.error("INDstocks: too many failures (%d), stopping", failed_windows)
                break
        except requests.Timeout as exc:
            logger.warning(
                "INDstocks historical timeout for %s %s (%s to %s): %s",
                scrip_code, api_interval, cursor.date(), end.date(), exc,
            )
            failed_windows += 1
            if failed_windows >= max_failures:
                logger.error("INDstocks: too many timeouts (%d), stopping", failed_windows)
                break
        except Exception as exc:
            logger.warning(
                "INDstocks historical error for %s %s (%s to %s): %s",
                scrip_code, api_interval, cursor.date(), end.date(), exc,
            )
            failed_windows += 1
            if failed_windows >= max_failures:
                break

        cursor = end
        # Small delay between paginated requests to respect rate limits (5 req/sec)
        _time.sleep(0.25)

    logger.info("INDstocks fetch_historical complete: %s %s returned %d candles",
                scrip_code, api_interval, len(all_candles))
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
    
    For F&O symbols (options/futures), attempts to find the tradingsymbol in the
    instruments cache. If not found, logs a warning.
    """
    sym_to_scrip: Dict[str, str] = {}
    for sym in symbols:
        try:
            sym_to_scrip[sym] = get_scrip_code(sym)
        except KeyError:
            # For F&O symbols, try looking up in the cache directly
            # Option symbols like NIFTY26N0322450PE may be in the FNO instruments
            cache = _instruments_cache()
            if sym.upper() in cache:
                sym_to_scrip[sym] = cache[sym.upper()]
            else:
                logger.warning(
                    "INDstocks: no scrip-code for '%s'. "
                    "If this is an F&O symbol, ensure INDMONEY_ACCESS_TOKEN is valid "
                    "and the instruments cache includes NFO segment.",
                    sym
                )

    if not sym_to_scrip:
        return {}

    scrip_to_ltp = fetch_ltp(list(sym_to_scrip.values()))
    return {
        sym: scrip_to_ltp[scrip]
        for sym, scrip in sym_to_scrip.items()
        if scrip in scrip_to_ltp
    }
