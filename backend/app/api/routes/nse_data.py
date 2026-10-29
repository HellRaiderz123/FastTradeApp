"""
NSE Live Data endpoints — Block/Bulk Deals, F&O Ban, Corporate Actions, Insider Trading, VIX.
All use the same Mac UA + page-specific Referer pattern that bypasses Akamai.
All endpoints are TTL-cached in-process to prevent backend flooding.
"""
import asyncio
import json as _json
import logging
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date as _date
from typing import Any, Dict, List, Optional, Tuple

import requests
from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/nse", tags=["nse_data"])

NSE_BASE = "https://www.nseindia.com"

_MAC_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Thread pool for blocking NSE HTTP calls — keeps FastAPI event loop free
_nse_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="nse-worker")

# ── In-process TTL cache ───────────────────────────────────────────────────
# { cache_key: (payload, expires_at_epoch) }
_CACHE: Dict[str, Tuple[Any, float]] = {}


def _cache_get(key: str) -> Any | None:
    entry = _CACHE.get(key)
    if entry and time.time() < entry[1]:
        return entry[0]
    return None


def _cache_set(key: str, value: Any, ttl_seconds: int) -> None:
    _CACHE[key] = (value, time.time() + ttl_seconds)


# Hard cap: each NSE fetch (direct + fallback) must finish within this budget
_NSE_FETCH_TIMEOUT = 8  # seconds — keeps total endpoint latency well under Render's 30s limit


def _nse_get(path: str, referer_path: str, params: dict | None = None) -> Any:
    """
    Fetch a JSON endpoint from NSE with the proven Mac UA + Referer pattern.
    Falls back to allorigins proxy on Akamai block (non-200).
    Hard-capped at _NSE_FETCH_TIMEOUT seconds total to prevent Render 502s.
    """
    url = f"{NSE_BASE}{path}"
    headers = {
        "User-Agent": _MAC_UA,
        "Accept": "application/json, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"{NSE_BASE}{referer_path}",
    }
    try:
        r = requests.get(url, headers=headers, params=params, timeout=_NSE_FETCH_TIMEOUT)
        if r.status_code == 200:
            return r.json()
        logger.warning("nse_data: direct fetch %s returned %s", path, r.status_code)
    except Exception as e:
        logger.warning("nse_data: direct fetch %s failed: %s", path, e)

    # allorigins proxy fallback — shorter timeout since we already spent some budget
    try:
        full_url = url if not params else url + "?" + urllib.parse.urlencode(params)
        proxy = f"https://api.allorigins.win/get?url={urllib.parse.quote(full_url, safe='')}"
        r = requests.get(proxy, timeout=_NSE_FETCH_TIMEOUT)
        if r.status_code == 200:
            contents = r.json().get("contents") or "null"
            return _json.loads(contents)
    except Exception as e:
        logger.warning("nse_data: allorigins fallback %s failed: %s", path, e)

    return None


# ── VIX (India VIX from NSE — no broker dependency) ───────────────────────

@router.get("/vix")
async def get_vix():
    """
    India VIX fetched directly from NSE. Cached 3 minutes.
    Avoids broker dependency (NIFTYVIX not in Zerodha token map).
    """
    cached = _cache_get("vix")
    if cached:
        return cached

    def _fetch_vix():
        vix_value = None
        try:
            data = _nse_get("/api/allIndices", "/market-data-pre-open/")
            if data and isinstance(data, dict):
                for idx in data.get("data") or []:
                    name = (idx.get("indexSymbol") or idx.get("index") or "").upper()
                    if "VIX" in name:
                        vix_value = float(idx.get("last") or idx.get("previousClose") or 0) or None
                        break
        except Exception as e:
            logger.warning("vix allIndices fetch error: %s", e)

        if not vix_value:
            try:
                data = _nse_get(
                    "/api/chart-databyindex",
                    "/market-data-pre-open/",
                    params={"index": "INDIAVIX"},
                )
                if data and isinstance(data, dict):
                    gd = data.get("grapthData") or data.get("graphData") or []
                    if gd:
                        vix_value = float(gd[-1][1]) if isinstance(gd[-1], list) else None
            except Exception as e:
                logger.warning("vix chart fallback error: %s", e)
        return vix_value

    loop = asyncio.get_running_loop()
    vix_value = await loop.run_in_executor(_nse_executor, _fetch_vix)

    if not vix_value:
        return {
            "current": None,
            "regime": "UNKNOWN",
            "implications": "VIX data temporarily unavailable",
            "timestamp": datetime.now().isoformat(),
        }

    if vix_value < 12:
        regime, implications = "VERY_CALM", "Market complacency. Low options premiums."
    elif vix_value < 15:
        regime, implications = "CALM", "Stable market. Good for selling premium strategies."
    elif vix_value < 20:
        regime, implications = "NORMAL", "Average volatility. Balanced risk environment."
    elif vix_value < 25:
        regime, implications = "ELEVATED", "Increased uncertainty. Higher options premiums."
    else:
        regime, implications = "HIGH_STRESS", "Market fear. Ideal for buying premium strategies."

    result = {
        "current": round(vix_value, 2),
        "regime": regime,
        "implications": implications,
        "timestamp": datetime.now().isoformat(),
    }
    _cache_set("vix", result, ttl_seconds=180)
    _persist_nse_snapshot("vix", result)
    return result


# ── Block & Bulk Deals ─────────────────────────────────────────────────────

@router.get("/block-deals")
async def get_block_deals():
    """NSE block/bulk deals for today. Cached 5 minutes."""
    cached = _cache_get("block_deals")
    if cached:
        return cached

    def _fetch():
        results: Dict[str, List] = {"block_deals": [], "bulk_deals": []}
        try:
            data = _nse_get("/api/block-deal", "/market-data-pre-open/block-deal")
            if data and isinstance(data, dict):
                for row in (data.get("data") or data.get("blockDeal") or []):
                    results["block_deals"].append({
                        "symbol":     row.get("symbol") or row.get("Symbol", ""),
                        "company":    row.get("name") or row.get("companyName", ""),
                        "client":     row.get("clientName") or row.get("client", ""),
                        "deal_type":  row.get("buySell") or row.get("dealType", ""),
                        "quantity":   row.get("quantity") or row.get("qty", 0),
                        "price":      row.get("price") or row.get("tradePrice", 0),
                        "trade_date": row.get("tradeDate") or row.get("date", ""),
                    })
        except Exception as e:
            logger.warning("block deals fetch error: %s", e)
        try:
            data = _nse_get("/api/bulk-deals", "/market-data-pre-open/bulk-deals")
            if data and isinstance(data, dict):
                for row in (data.get("data") or data.get("bulkDeal") or []):
                    results["bulk_deals"].append({
                        "symbol":     row.get("symbol") or row.get("Symbol", ""),
                        "company":    row.get("name") or row.get("companyName", ""),
                        "client":     row.get("clientName") or row.get("client", ""),
                        "deal_type":  row.get("buySell") or row.get("dealType", ""),
                        "quantity":   row.get("quantity") or row.get("qty", 0),
                        "price":      row.get("price") or row.get("tradePrice", 0),
                        "trade_date": row.get("tradeDate") or row.get("date", ""),
                    })
        except Exception as e:
            logger.warning("bulk deals fetch error: %s", e)
        return results

    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(_nse_executor, _fetch)
    results["total"] = len(results["block_deals"]) + len(results["bulk_deals"])
    results["timestamp"] = datetime.now().isoformat()
    _cache_set("block_deals", results, ttl_seconds=300)
    _persist_nse_snapshot("block_deals", results)
    return results


# ── F&O Ban List ───────────────────────────────────────────────────────────

@router.get("/fo-ban")
async def get_fo_ban():
    """Stocks in F&O ban period (MWPL > 95%). Cached 10 minutes."""
    cached = _cache_get("fo_ban")
    if cached:
        return cached

    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(
        _nse_executor,
        lambda: _nse_get("/api/fo-sec-ban", "/market-data-pre-open/fo-sec-ban"),
    )

    banned: List[str] = []
    if data:
        if isinstance(data, list):
            banned = [str(s).strip().upper() for s in data if s]
        elif isinstance(data, dict):
            raw = data.get("data") or data.get("secBanList") or []
            banned = [str(s).strip().upper() for s in raw if s]

    result = {
        "banned_symbols": banned,
        "count": len(banned),
        "note": "Fresh F&O positions cannot be opened in these stocks (MWPL > 95%)",
        "timestamp": datetime.now().isoformat(),
    }
    _cache_set("fo_ban", result, ttl_seconds=600)
    _persist_nse_snapshot("fo_ban", result)
    return result


# ── Corporate Actions ──────────────────────────────────────────────────────

@router.get("/corporate-actions")
async def get_corporate_actions(days_ahead: int = 30):
    """Upcoming dividends, bonus, splits, rights, board meetings from NSE. Cached 15 minutes."""
    cache_key = f"corp_actions_{days_ahead}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    actions: List[Dict] = []

    try:
        data = _nse_get(
            "/api/corporates-corporateActions",
            "/companies-listing/corporate-filings-corporate-actions",
            params={"index": "equities"},
        )
        if data:
            for row in (data if isinstance(data, list) else data.get("data") or [])[:60]:
                actions.append({
                    "type":        "corporate_action",
                    "action_type": row.get("purpose") or row.get("subject") or "Corporate Action",
                    "symbol":      row.get("symbol", ""),
                    "company":     row.get("companyName") or row.get("name", ""),
                    "ex_date":     row.get("exDate") or row.get("exDt") or "",
                    "record_date": row.get("recordDate") or row.get("recDt") or "",
                    "details":     row.get("remarks") or row.get("details") or "",
                    "series":      row.get("series", "EQ"),
                })
    except Exception as e:
        logger.warning("corporate actions fetch error: %s", e)

    try:
        data = _nse_get(
            "/api/corporate-board-meetings",
            "/companies-listing/corporate-filings-board-meetings",
            params={"index": "equities"},
        )
        if data:
            for row in (data if isinstance(data, list) else data.get("data") or [])[:40]:
                actions.append({
                    "type":        "board_meeting",
                    "action_type": row.get("purpose") or "Board Meeting",
                    "symbol":      row.get("symbol", ""),
                    "company":     row.get("companyName") or row.get("name", ""),
                    "ex_date":     row.get("meetingDate") or row.get("bm_date") or "",
                    "record_date": "",
                    "details":     row.get("purpose") or row.get("description") or "",
                    "series":      row.get("series", "EQ"),
                })
    except Exception as e:
        logger.warning("board meetings fetch error: %s", e)

    result = {"actions": actions, "count": len(actions), "timestamp": datetime.now().isoformat()}
    _cache_set(cache_key, result, ttl_seconds=900)
    _persist_nse_snapshot("corporate_actions", result)
    return result


# ── Company Announcements (NSE filings) ──────────────────────────────────

@router.get("/announcements")
async def get_announcements(symbol: str = ""):
    """
    NSE corporate announcements for a symbol (or latest 50 if no symbol).
    Cached 10 minutes per symbol.
    """
    cache_key = f"announcements_{symbol.upper()}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    sym = symbol.upper().strip()

    def _fetch():
        params = {"index": "equities"}
        if sym:
            params["symbol"] = sym
        return _nse_get(
            "/api/corporate-announcements",
            "/companies-listing/corporate-filings-announcements",
            params=params,
        )

    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(_nse_executor, _fetch)

    items: List[Dict] = []
    rows = data if isinstance(data, list) else (data.get("data") or [] if data else [])
    for row in rows[:60]:
        s = (row.get("symbol") or "").strip()
        if sym and s.upper() != sym:
            continue
        headline = (
            row.get("desc") or row.get("attchmntText") or
            row.get("subject") or row.get("purpose") or ""
        ).strip()
        if not headline:
            continue
        items.append({
            "symbol":       s or sym,
            "company":      row.get("sm_name") or row.get("companyName") or s,
            "headline":     headline,
            "category":     row.get("attchmntType") or row.get("category") or "Announcement",
            "pdf_url":      row.get("attchmntFile") or row.get("pdfUrl"),
            "published_at": row.get("sort_date") or row.get("date") or datetime.now().isoformat(),
            "source":       "NSE",
        })

    result = {"data": items, "count": len(items), "symbol": sym, "timestamp": datetime.now().isoformat()}
    _cache_set(cache_key, result, ttl_seconds=600)
    if not sym:  # only persist the "all announcements" snapshot, not per-symbol
        _persist_nse_snapshot("announcements", result)
    return result


# ── Insider Trading / SAST ─────────────────────────────────────────────────

@router.get("/insider-trading")
async def get_insider_trading():
    """
    Promoter/insider shareholding changes via NSE SAST disclosures.
    Tries two NSE endpoints. Cached 5 minutes.
    """
    cached = _cache_get("insider_trading")
    if cached:
        return cached

    def _fetch():
        raw_rows: List[Dict] = []
        # NSE renamed /api/corporates-sast — try both current paths
        for sast_path, sast_referer, sast_params in [
            ("/api/corporate-announcements", "/companies-listing/corporate-filings-announcements", {"index": "sast"}),
            ("/api/corporates-sast", "/companies-listing/corporate-filings-insider-trading", None),
        ]:
            try:
                data = _nse_get(sast_path, sast_referer, params=sast_params)
                if data:
                    raw_rows = data if isinstance(data, list) else (data.get("data") or [])
                if raw_rows:
                    break
            except Exception as e:
                logger.warning("insider fetch %s error: %s", sast_path, e)
        return raw_rows

    loop = asyncio.get_running_loop()
    raw_rows = await loop.run_in_executor(_nse_executor, _fetch)

    items: List[Dict] = []
    for row in raw_rows[:50]:
        symbol = (row.get("symbol") or row.get("Symbol") or "").strip()
        headline = (
            row.get("desc") or row.get("attchmntText") or
            row.get("subject") or row.get("purpose") or ""
        )
        if not symbol:
            continue

        hl_lower = headline.lower()
        if any(w in hl_lower for w in ["acqui", "purchas", "bought", "buy", "increase", "crept"]):
            direction = "BUY"
        elif any(w in hl_lower for w in ["sell", "sold", "decreas", "dispos", "reduc"]):
            direction = "SELL"
        else:
            direction = "CHANGE"

        items.append({
            "symbol":       symbol,
            "company":      row.get("sm_name") or row.get("companyName") or row.get("name") or symbol,
            "headline":     headline or "SAST Disclosure",
            "direction":    direction,
            "pdf_url":      row.get("attchmntFile") or row.get("pdfUrl"),
            "published_at": row.get("sort_date") or row.get("date") or datetime.now().isoformat(),
            "category":     "Insider / SAST",
        })

    result = {"data": items, "count": len(items), "timestamp": datetime.now().isoformat()}
    _cache_set("insider_trading", result, ttl_seconds=300)
    _persist_nse_snapshot("insider_trading", result)
    return result


# ── Short Selling ────────────────────────────────────────────────────────────

@router.get("/short-selling")
async def get_short_selling():
    """NSE short selling data. Cached 10 minutes."""
    cached = _cache_get("short_selling")
    if cached:
        return cached

    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(
        _nse_executor,
        lambda: _nse_get("/api/short-selling", "/market-data-pre-open/short-selling"),
    )

    items: List[Dict] = []
    rows = data if isinstance(data, list) else (data.get("data") or [] if data else [])
    for row in rows[:100]:
        symbol = (row.get("symbol") or row.get("Symbol") or "").strip().upper()
        if not symbol:
            continue
        items.append({
            "symbol":       symbol,
            "company":      row.get("companyName") or row.get("name") or symbol,
            "quantity":     row.get("shortSellQty") or row.get("quantity") or 0,
            "trade_date":   row.get("tradeDate") or row.get("date") or "",
            "series":       row.get("series") or "EQ",
        })

    result = {"data": items, "count": len(items), "timestamp": datetime.now().isoformat()}
    _cache_set("short_selling", result, ttl_seconds=600)
    _persist_nse_snapshot("short_selling", result)
    return result


# ── Participant-wise OI ────────────────────────────────────────────────────────

@router.get("/participant-oi")
async def get_participant_oi():
    """FII/DII/Pro/Client participant-wise OI in index & stock F&O. Cached 10 minutes."""
    cached = _cache_get("participant_oi")
    if cached:
        return cached

    def _fetch():
        results = {}
        for key, params in [
            ("index_futures",  {"type": "index",  "instrument": "FUTSTK"}),
            ("stock_futures",  {"type": "equity", "instrument": "FUTSTK"}),
            ("index_options",  {"type": "index",  "instrument": "OPTSTK"}),
        ]:
            try:
                data = _nse_get(
                    "/api/participant-wise-trading-data",
                    "/market-data-pre-open/derivatives",
                    params=params,
                )
                if data:
                    rows = data if isinstance(data, list) else (data.get("data") or [])
                    results[key] = [
                        {
                            "client_type": r.get("clientType") or r.get("client_type") or "",
                            "buy_contracts": r.get("buyContracts") or r.get("buy") or 0,
                            "sell_contracts": r.get("sellContracts") or r.get("sell") or 0,
                            "net_contracts": r.get("netContracts") or r.get("net") or 0,
                            "oi_long": r.get("openInterestLong") or r.get("oi_long") or 0,
                            "oi_short": r.get("openInterestShort") or r.get("oi_short") or 0,
                            "oi_net": r.get("openInterestNet") or r.get("oi_net") or 0,
                        }
                        for r in rows
                    ]
            except Exception as e:
                logger.warning("participant OI %s error: %s", key, e)
                results[key] = []
        return results

    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(_nse_executor, _fetch)
    results["timestamp"] = datetime.now().isoformat()
    _cache_set("participant_oi", results, ttl_seconds=600)
    _persist_nse_snapshot("participant_oi", results)
    return results


# ── Forthcoming Corporate Actions ─────────────────────────────────────────────

@router.get("/forthcoming-actions")
async def get_forthcoming_actions():
    """Upcoming dividends, splits, bonus before ex-date. Cached 30 minutes."""
    cached = _cache_get("forthcoming_actions")
    if cached:
        return cached

    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(
        _nse_executor,
        lambda: _nse_get(
            "/api/corporates-forthcoming",
            "/companies-listing/corporate-filings-corporate-actions",
            params={"index": "equities"},
        ),
    )

    items: List[Dict] = []
    rows = data if isinstance(data, list) else (data.get("data") or [] if data else [])
    for row in rows[:80]:
        symbol = (row.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        items.append({
            "symbol":      symbol,
            "company":     row.get("companyName") or row.get("name") or symbol,
            "action_type": row.get("purpose") or row.get("subject") or "Corporate Action",
            "ex_date":     row.get("exDate") or row.get("exDt") or "",
            "record_date": row.get("recordDate") or row.get("recDt") or "",
            "details":     row.get("remarks") or row.get("details") or "",
            "series":      row.get("series") or "EQ",
        })

    result = {"data": items, "count": len(items), "timestamp": datetime.now().isoformat()}
    _cache_set("forthcoming_actions", result, ttl_seconds=1800)
    _persist_nse_snapshot("forthcoming_actions", result)
    return result


# ── 52-Week High / Low Movers ─────────────────────────────────────────────────

@router.get("/52week")
async def get_52week_movers():
    """Stocks hitting 52-week highs and lows today. Cached 15 minutes."""
    cached = _cache_get("52week")
    if cached:
        return cached

    def _fetch():
        highs, lows = [], []
        for category, bucket in [("52W_HIGH", highs), ("52W_LOW", lows)]:
            try:
                data = _nse_get(
                    "/api/live-analysis-data",
                    "/market-data-pre-open/",
                    params={"index": category},
                )
                rows = data if isinstance(data, list) else (data.get("data") or [] if data else [])
                for r in rows[:50]:
                    symbol = (r.get("symbol") or r.get("Symbol") or "").strip().upper()
                    if not symbol:
                        continue
                    bucket.append({
                        "symbol":  symbol,
                        "company": r.get("companyName") or r.get("name") or symbol,
                        "ltp":     r.get("lastPrice") or r.get("ltp") or 0,
                        "high52":  r.get("yearHigh") or r.get("52wHigh") or 0,
                        "low52":   r.get("yearLow") or r.get("52wLow") or 0,
                        "change_pct": r.get("pChange") or r.get("changePct") or 0,
                    })
            except Exception as e:
                logger.warning("52week %s error: %s", category, e)
        return {"highs": highs, "lows": lows}

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(_nse_executor, _fetch)
    result["timestamp"] = datetime.now().isoformat()
    _cache_set("52week", result, ttl_seconds=900)
    _persist_nse_snapshot("52week", result)
    return result


# ── Market Turnover ───────────────────────────────────────────────────────────

@router.get("/market-turnover")
async def get_market_turnover():
    """Daily cash + F&O market turnover. Cached 15 minutes."""
    cached = _cache_get("market_turnover")
    if cached:
        return cached

    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(
        _nse_executor,
        lambda: _nse_get("/api/market-turnover", "/market-data-pre-open/"),
    )

    result: Dict = {"cash": {}, "fno": {}, "raw": data, "timestamp": datetime.now().isoformat()}
    if data and isinstance(data, dict):
        result["cash"] = {
            "total_turnover": data.get("totalTurnover") or data.get("cashTurnover") or 0,
            "traded_value":   data.get("tradedValue") or 0,
            "date":           data.get("date") or "",
        }
        result["fno"] = {
            "futures_turnover": data.get("futuresTurnover") or 0,
            "options_turnover": data.get("optionsTurnover") or 0,
            "total_fno":        data.get("totalFnoTurnover") or 0,
        }

    _cache_set("market_turnover", result, ttl_seconds=900)
    _persist_nse_snapshot("market_turnover", result)
    return result


# ── F&O Ban History ───────────────────────────────────────────────────────────

@router.get("/ban-history")
async def get_ban_history():
    """
    Tracks F&O ban entries/exits by comparing today's ban list against yesterday's.
    Cached 10 minutes.
    """
    cached = _cache_get("ban_history")
    if cached:
        return cached

    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(
        _nse_executor,
        lambda: _nse_get("/api/fo-sec-ban", "/market-data-pre-open/fo-sec-ban"),
    )

    current: List[str] = []
    if data:
        if isinstance(data, list):
            current = [str(s).strip().upper() for s in data if s]
        elif isinstance(data, dict):
            current = [str(s).strip().upper() for s in (data.get("data") or data.get("secBanList") or []) if s]

    # Load previous snapshot from cache key "ban_prev"
    prev_entry = _CACHE.get("ban_prev")
    previous: List[str] = prev_entry[0] if prev_entry else []

    entered = [s for s in current if s not in previous]
    exited  = [s for s in previous if s not in current]

    # Save current as new previous
    _cache_set("ban_prev", current, ttl_seconds=86400)

    result = {
        "current": current,
        "entered_today": entered,
        "exited_today": exited,
        "count": len(current),
        "timestamp": datetime.now().isoformat(),
    }
    _cache_set("ban_history", result, ttl_seconds=600)
    _persist_nse_snapshot("ban_history", result)
    return result


# ── DB persistence helper ─────────────────────────────────────────────────

def _persist_nse_snapshot(data_type: str, payload: Any) -> None:
    """
    Upsert a snapshot row for today into nse_snapshots.
    Called after every successful live fetch so the DB always has the latest.
    """
    try:
        from app.db.session import SessionLocal
        from app.db.models_nse import NseSnapshot
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy import text

        today = _date.today()
        db = SessionLocal()
        try:
            existing = (
                db.query(NseSnapshot)
                .filter(NseSnapshot.data_type == data_type, NseSnapshot.trade_date == today)
                .first()
            )
            if existing:
                existing.payload = payload
                existing.fetched_at = datetime.now()
            else:
                db.add(NseSnapshot(data_type=data_type, trade_date=today, payload=payload))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.warning("nse_data: DB persist failed for %s: %s", data_type, e)


# ── History read endpoint ──────────────────────────────────────────────────

@router.get("/snapshots/{data_type}")
async def get_nse_snapshots(
    data_type: str,
    days: int = Query(30, ge=1, le=365, description="How many days of history to return"),
):
    """
    Return stored NSE snapshots for a given data_type.
    data_type: vix | block_deals | fo_ban | corporate_actions | announcements |
               insider_trading | short_selling | participant_oi |
               forthcoming_actions | 52week | market_turnover | ban_history
    """
    from app.db.session import SessionLocal
    from app.db.models_nse import NseSnapshot
    from datetime import timedelta

    db = SessionLocal()
    try:
        cutoff = _date.today() - timedelta(days=days)
        rows = (
            db.query(NseSnapshot)
            .filter(
                NseSnapshot.data_type == data_type,
                NseSnapshot.trade_date >= cutoff,
            )
            .order_by(NseSnapshot.trade_date.desc())
            .all()
        )
        return {
            "data_type": data_type,
            "count": len(rows),
            "snapshots": [
                {
                    "trade_date": str(r.trade_date),
                    "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
                    "payload": r.payload,
                }
                for r in rows
            ],
        }
    finally:
        db.close()


# ── Debug: manually trigger NSE filing alert job ───────────────────────────

@router.post("/filing-alerts/run-now")
async def run_filing_alerts_now():
    """
    Manually trigger the NSE filing alert job once.
    Clears the dedup cache first so all current filings are re-evaluated.
    Returns a summary of what was found and sent.
    """
    from app.core.market.scheduler import (
        _check_nse_high_impact_filings,
        _NOTIFIED_FILINGS,
        _classify_filing_impact,
    )
    import os

    # Clear dedup so we can see what would fire right now
    _NOTIFIED_FILINGS.clear()

    # Check Telegram config
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    tg_chat = os.getenv("TELEGRAM_CHAT_ID", "")

    # Fetch raw data to show what the job sees
    data = _nse_get(
        "/api/corporate-announcements",
        "/companies-listing/corporate-filings-announcements",
        params={"index": "equities"},
    )
    rows = data if isinstance(data, list) else (data.get("data") or [] if data else [])

    preview = []
    for row in rows[:20]:
        symbol = (row.get("symbol") or "").strip().upper()
        headline = (
            row.get("desc") or row.get("attchmntText") or
            row.get("subject") or row.get("purpose") or ""
        ).strip()
        category = (row.get("attchmntType") or row.get("category") or "Announcement").strip()
        if symbol and headline:
            preview.append({
                "symbol": symbol,
                "headline": headline[:100],
                "category": category,
                "impact": _classify_filing_impact(headline, category),
            })

    # Now actually run the job (will send Telegram for HIGH/MEDIUM)
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _check_nse_high_impact_filings)

    high_medium = [p for p in preview if p["impact"] in ("HIGH", "MEDIUM")]

    return {
        "telegram_configured": bool(tg_token and tg_chat),
        "raw_rows_fetched": len(rows),
        "preview_sample": preview,
        "high_medium_count": len(high_medium),
        "high_medium_filings": high_medium,
        "job_triggered": True,
        "timestamp": datetime.now().isoformat(),
    }
