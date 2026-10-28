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
from datetime import datetime
from typing import Any, Dict, List, Tuple

import requests
from fastapi import APIRouter

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


def _nse_get(path: str, referer_path: str, params: dict | None = None) -> Any:
    """
    Fetch a JSON endpoint from NSE with the proven Mac UA + Referer pattern.
    Falls back to allorigins proxy on Akamai block (non-200).
    """
    url = f"{NSE_BASE}{path}"
    headers = {
        "User-Agent": _MAC_UA,
        "Accept": "application/json, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"{NSE_BASE}{referer_path}",
    }
    try:
        r = requests.get(url, headers=headers, params=params, timeout=20)
        if r.status_code == 200:
            return r.json()
        logger.warning("nse_data: direct fetch %s returned %s", path, r.status_code)
    except Exception as e:
        logger.warning("nse_data: direct fetch %s failed: %s", path, e)

    # allorigins proxy fallback
    try:
        full_url = url if not params else url + "?" + urllib.parse.urlencode(params)
        proxy = f"https://api.allorigins.win/get?url={urllib.parse.quote(full_url, safe='')}"
        r = requests.get(proxy, timeout=30)
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
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="VIX data temporarily unavailable")

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
            data = _nse_get("/api/bulk-deal", "/market-data-pre-open/bulk-deal")
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
        lambda: _nse_get("/api/fo-secban", "/market-data-pre-open/fo-sec-ban"),
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
        try:
            data = _nse_get(
                "/api/corporates-sast",
                "/companies-listing/corporate-filings-insider-trading",
            )
            if data:
                raw_rows = data if isinstance(data, list) else (data.get("data") or [])
        except Exception as e:
            logger.warning("insider sast primary error: %s", e)

        if not raw_rows:
            try:
                data = _nse_get(
                    "/api/corporate-announcements",
                    "/companies-listing/corporate-filings-announcements",
                    params={"index": "sast"},
                )
                if data:
                    raw_rows = data if isinstance(data, list) else (data.get("data") or [])
            except Exception as e:
                logger.warning("insider announcements fallback error: %s", e)
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
    return result
