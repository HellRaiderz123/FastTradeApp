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
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.indstocks.com"

# ── Rate Limiter ───────────────────────────────────────────────────────────
# INDstocks rate limits: 5 requests/second, 100k requests/day
# We'll be conservative: 4 req/sec with 250ms minimum between requests

class RateLimiter:
    """Simple token bucket rate limiter for INDstocks API."""
    
    def __init__(self, requests_per_second: float = 4.0, min_interval: float = 0.25):
        self.min_interval = max(min_interval, 1.0 / requests_per_second)
        self.last_request_time = 0.0
        self._lock = threading.Lock()
    
    def wait(self):
        """Block until it's safe to make another request."""
        with self._lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                time.sleep(sleep_time)
            self.last_request_time = time.time()


# Global rate limiter instance
_rate_limiter = RateLimiter(requests_per_second=4.0, min_interval=0.25)

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


# Cache token to avoid DB query on every API call
_cached_token: str = ""
_cached_token_expires: float = 0.0


def _access_token() -> str:
    """
    Get INDMoney access token.
    
    Priority:
      1. In-memory cache (valid for 5 minutes)
      2. Database (INDMoneySession with is_active=1 and not expired)
      3. Environment variable INDMONEY_ACCESS_TOKEN
    """
    global _cached_token, _cached_token_expires
    
    # Return cached token if still valid
    if _cached_token and time.time() < _cached_token_expires:
        return _cached_token
    
    # Try database first (token saved via settings endpoint)
    try:
        from app.db.session import SessionLocal
        from app.db.models_indmoney import INDMoneySession
        from datetime import datetime
        
        db = SessionLocal()
        try:
            session = (
                db.query(INDMoneySession)
                .filter(INDMoneySession.is_active == 1)
                .order_by(INDMoneySession.created_at.desc())
                .first()
            )
            if session and session.access_token:
                # Check if not expired (handle both naive and aware datetimes)
                now_utc = datetime.utcnow()
                expires_at = session.expires_at
                if expires_at is not None:
                    # Make comparison timezone-naive
                    if expires_at.tzinfo is not None:
                        expires_at = expires_at.replace(tzinfo=None)
                
                if expires_at is None or expires_at > now_utc:
                    logger.info("INDMoney token loaded from database (expires: %s)", session.expires_at)
                    _cached_token = session.access_token
                    _cached_token_expires = time.time() + 300  # Cache for 5 minutes
                    return _cached_token
                else:
                    logger.warning("INDMoney token from DB expired at %s", session.expires_at)
        finally:
            db.close()
    except Exception as e:
        logger.warning("Could not read INDMoney token from DB: %s", e)
    
    # Fallback to environment variable
    token = os.getenv("INDMONEY_ACCESS_TOKEN", "")
    if token:
        logger.info("INDMoney token loaded from .env (length: %d)", len(token))
        _cached_token = token
        _cached_token_expires = time.time() + 300
        return _cached_token
    
    raise RuntimeError(
        "INDMONEY_ACCESS_TOKEN not found. "
        "Save token via Settings > INDMoney or set INDMONEY_ACCESS_TOKEN in .env"
    )


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
            # Rate limit before each request
            _rate_limiter.wait()
            
            resp = requests.get(
                f"{BASE_URL}/market/instruments",
                params={"source": source},
                headers=_headers(),
                timeout=15,
            )
            
            # Handle rate limiting
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 2))
                logger.warning("INDstocks instruments rate limited, waiting %ds", retry_after)
                time.sleep(retry_after)
                continue
                
            resp.raise_for_status()
            reader = csv.DictReader(io.StringIO(resp.text))
            rows_loaded = 0
            for row in reader:
                if source == "index":
                    exch = (row.get("EXCH") or "NSE").strip().upper()
                    sid = (row.get("SECURITY_ID") or "").strip()
                    sym = (row.get("SEGMENT") or "").strip().upper()
                    if sym and sid:
                        merged[sym] = f"{exch}_{sid}"
                        rows_loaded += 1
                else:
                    exch = (row.get("EXCH") or "NSE").strip().upper()
                    sid = (row.get("SECURITY_ID") or "").strip()
                    sym = (row.get("TRADING_SYMBOL") or "").strip().upper()
                    if sym and sid:
                        # F&O instruments use NFO segment prefix
                        segment = "NFO" if source == "fno" else exch
                        scrip = f"{segment}_{sid}"
                        # NSE always wins over BSE for dual-listed stocks
                        if sym not in merged or exch == "NSE":
                            merged[sym] = scrip
                        rows_loaded += 1
                        # For F&O, also index by a normalised lookup key so
                        # build_option_symbol() can find it without knowing the
                        # exact TRADING_SYMBOL string.
                        # Key format: UNDERLYING|EXPIRY_DATE|STRIKE|OPTTYPE
                        # e.g. "NIFTY|2026-11-03|22500|PE"
                        if source == "fno":
                            try:
                                underlying_name = (row.get("UNDERLYING_SCRIP_NAME") or "").strip().upper()
                                strike_raw = (row.get("STRIKE_PRICE") or "").strip()
                                opt_type = (row.get("OPTION_TYPE") or "").strip().upper()
                                expiry_raw = (row.get("EXPIRY_DATE") or "").strip()  # MM/DD/YYYY HH:MM
                                if underlying_name and strike_raw and opt_type and expiry_raw:
                                    from datetime import datetime as _dt
                                    exp_date = _dt.strptime(expiry_raw.split()[0], "%m/%d/%Y").date()
                                    strike_int = int(float(strike_raw))
                                    lookup_key = f"{underlying_name}|{exp_date}|{strike_int}|{opt_type}"
                                    merged[lookup_key] = scrip
                            except Exception:
                                pass
            logger.info("INDstocks instruments loaded source=%s: %d rows", source, rows_loaded)
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
# Keys match what callers pass; values match SEGMENT column in INDstocks index CSV (uppercased)
_INDEX_ALIASES: Dict[str, str] = {
    "NIFTY":     "NIFTY 50",
    "BANKNIFTY": "BANK NIFTY",
    "FINNIFTY":  "NIFTYFINSRV25 50",
    "NIFTYVIX":  "INDIA VIX",
}

# Hardcoded fallback scrip-codes.
# Covers indices + full NIFTY 100 / scheduler symbol list.
# Security IDs sourced from INDstocks instrument CSV (NSE equity segment).
_INDEX_FALLBACK_SCRIP: Dict[str, str] = {
    # ── Indices (SECURITY_IDs from INDstocks /market/instruments?source=index) ──
    "NIFTY 50":          "NSE_40000001",
    "NIFTY":             "NSE_40000001",
    "BANK NIFTY":        "NSE_40000003",  # exact CSV name
    "NIFTY BANK":        "NSE_40000003",  # legacy alias
    "BANKNIFTY":         "NSE_40000003",
    "NIFTY IT":          "NSE_40000004",
    "NIFTYFINSRV25 50":  "NSE_40000076",  # exact CSV name (uppercased)
    "NIFTY FIN SERVICE": "NSE_40000076",  # legacy alias
    "FINNIFTY":          "NSE_40000076",
    "INDIA VIX":         "NSE_40000107",
    "NIFTYVIX":          "NSE_40000107",
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
    # DRREDDY, EICHERMOT - use live instruments API (hardcoded IDs return 400)
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
    # HAL - use live instruments API (ID may vary)
    "BEL":         "NSE_383",
    "BHEL":        "NSE_438",
    # ── Consumer / Retail ─────────────────────────────────────────────────
    "PIDILITIND":  "NSE_2664",
    "HAVELLS":     "NSE_14419",
    "VOLTAS":      "NSE_3718",
    "DMART":       "NSE_21780",
    "TRENT":       "NSE_3519",
    # ZOMATO/ETERNAL, IRCTC, PAYTM - use live instruments API (IDs change frequently)
    "TATAMOTORS":  "NSE_3456",
    "SHRIRAMFIN":  "NSE_4306",
    # ── Real Estate ───────────────────────────────────────────────────────
    "DLF":         "NSE_14732",
    # OBEROIRLTY - use live instruments API
    # ── Telecom ───────────────────────────────────────────────────────────
    "IDEA":        "NSE_14366",
    # ── Chemicals ─────────────────────────────────────────────────────────
    "SRF":         "NSE_3273",
    "DEEPAKNTR":   "NSE_7927",
    "TATACHEM":    "NSE_3405",
    # ── Misc ──────────────────────────────────────────────────────────────
    "NAUKRI":      "NSE_13751",
    # JIOFIN - use live instruments API (new listing, ID may vary)
}


def get_scrip_code(symbol: str) -> str:
    """
    Resolve a plain symbol to an INDstocks scrip-code (e.g. NSE_2885).

    Lookup order:
      1. DB instruments table (synced from live API — always up to date)
      2. In-memory instruments cache (15-min TTL, from API CSV)
      3. Hardcoded fallback map (emergency only — last resort)
    """
    sym = symbol.upper().strip()

    # 1. DB lookup — live contract, no hardcoding needed
    try:
        from app.core.broker.indstocks.instruments_sync import get_scrip_code_from_db
        scrip = get_scrip_code_from_db(sym)
        if scrip:
            return scrip
    except Exception:
        pass  # DB unavailable — fall through

    # 2. In-memory cache (populated from API CSV)
    cache = _instruments_cache()
    scrip = cache.get(sym)
    if scrip:
        return scrip
    alias = _INDEX_ALIASES.get(sym)
    if alias:
        scrip = cache.get(alias.upper())
        if scrip:
            return scrip

    # 3. Hardcoded fallback — emergency only
    scrip = _INDEX_FALLBACK_SCRIP.get(sym)
    if scrip:
        return scrip
    if alias:
        scrip = _INDEX_FALLBACK_SCRIP.get(alias.upper())
        if scrip:
            return scrip

    raise KeyError(
        f"INDstocks scrip-code not found for '{symbol}'. "
        "Ensure INDMONEY_ACCESS_TOKEN is set and instruments are synced."
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
    Rate limited to 4 req/sec.
    
    Returns list of dicts: {date, open, high, low, close, volume}
    """
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
        
        # Rate limit before each request
        _rate_limiter.wait()
        
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
            
            # Handle rate limiting
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 2))
                logger.warning("INDstocks historical rate limited, waiting %ds", retry_after)
                time.sleep(retry_after)
                continue  # Retry same window
            
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
        # Rate limiter handles timing between requests

    logger.info("INDstocks fetch_historical complete: %s %s returned %d candles",
                scrip_code, api_interval, len(all_candles))
    return all_candles


# ── Live LTP ───────────────────────────────────────────────────────────────

def fetch_ltp(scrip_codes: List[str]) -> Dict[str, float]:
    """
    Fetch last traded price for a list of scrip-codes.

    Per docs: GET /market/quotes/ltp
    Response: {"status": "success", "data": {"NSE_3045": {"live_price": 792.5}}}
    
    Rate limit: 5 req/sec (we use 4 req/sec to be safe)

    Returns {scrip_code: ltp}.
    """
    if not scrip_codes:
        return {}

    result: Dict[str, float] = {}
    # API accepts up to 1000 per call per docs; batch at 50 to stay safe
    for i in range(0, len(scrip_codes), 50):
        batch = scrip_codes[i: i + 50]
        
        # Wait for rate limiter before making request
        _rate_limiter.wait()
        
        try:
            resp = requests.get(
                f"{BASE_URL}/market/quotes/ltp",
                params={"scrip-codes": ",".join(batch)},
                headers=_headers(),
                timeout=10,
            )
            
            # Handle rate limit response specifically
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 2))
                logger.warning("INDstocks rate limited (429), waiting %ds before retry", retry_after)
                time.sleep(retry_after)
                # Retry once after waiting
                _rate_limiter.wait()
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
                    
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            if status == 429:
                logger.warning("INDstocks LTP rate limited (429) for batch, skipping")
            elif status == 400:
                # Bad request - likely invalid scrip code
                logger.warning("INDstocks LTP bad request (400) for batch %s: %s", 
                             batch[:3], exc.response.text[:200] if exc.response else "")
            else:
                logger.warning("INDstocks LTP fetch error: %s", exc)
        except Exception as exc:
            logger.warning("INDstocks LTP fetch error: %s", exc)

    return result


def fetch_ltp_by_symbol(symbols: List[str]) -> Dict[str, float]:
    """
    Convenience: resolve symbols -> scrip-codes -> LTP -> return keyed by original symbol.
    
    For F&O symbols (options/futures), attempts to find the tradingsymbol in the
    instruments cache. If not found, skips silently (these symbols need live API).
    """
    sym_to_scrip: Dict[str, str] = {}
    skipped: List[str] = []
    
    for sym in symbols:
        try:
            sym_to_scrip[sym] = get_scrip_code(sym)
        except KeyError:
            # For F&O symbols, try looking up in the cache directly
            cache = _instruments_cache()
            if sym.upper() in cache:
                sym_to_scrip[sym] = cache[sym.upper()]
            else:
                skipped.append(sym)
    
    # Log skipped symbols only once per batch (reduce log spam)
    if skipped and len(skipped) <= 5:
        logger.debug("INDstocks: skipped symbols without scrip-code: %s", skipped)
    elif skipped:
        logger.debug("INDstocks: skipped %d symbols without scrip-code", len(skipped))

    if not sym_to_scrip:
        return {}

    scrip_to_ltp = fetch_ltp(list(sym_to_scrip.values()))
    return {
        sym: scrip_to_ltp[scrip]
        for sym, scrip in sym_to_scrip.items()
        if scrip in scrip_to_ltp
    }
