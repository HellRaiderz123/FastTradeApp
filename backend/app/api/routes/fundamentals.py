"""
Fundamentals API — powered by yashsarawgi.me Indian Stocks Fundamentals API.
Caches responses in DB for 90 days (quarterly result cadence).
Endpoints:
  GET /api/fundamentals/{symbol}          — fetch + cache fundamentals
  POST /api/fundamentals/{symbol}/refresh — force-refresh cache
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional

import requests as _req
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fundamentals", tags=["fundamentals"])

FUNDAMENTALS_API_KEY = os.getenv("FUNDAMENTALS_API_KEY", "ys_live_f77afa06dd07591242432f9fa22a0d31")
FUNDAMENTALS_BASE_URL = "https://yashsarawgi.me/api/v1/fundamentals/stock"
CACHE_TTL_DAYS = 90  # refresh after ~quarterly results


def _parse_float(val: Any) -> Optional[float]:
    try:
        return float(str(val).replace(",", "")) if val is not None else None
    except Exception:
        return None


def _parse_52w(raw: str) -> tuple[Optional[float], Optional[float]]:
    """Parse '3,350 / 2,000' → (3350.0, 2000.0)"""
    try:
        parts = raw.replace(",", "").split("/")
        if len(parts) == 2:
            return _parse_float(parts[0].strip()), _parse_float(parts[1].strip())
    except Exception:
        pass
    return None, None


def _latest_year_val(rows_by_item: dict, item: str) -> Optional[float]:
    """Get the most recent non-TTM annual value for a P&L/BS line item."""
    row = rows_by_item.get(item) or {}
    years = sorted([k for k in row if k.startswith("Mar")], reverse=True)
    for y in years:
        v = _parse_float(str(row[y]).replace("%", "") if row[y] is not None else None)
        if v is not None:
            return v
    return None


def _extract_financials(stock: dict) -> dict:
    """Extract computed metrics and rich sections from the stock object."""
    d = stock.get("data") or {}
    pnl_rows = {r["line_item"]: r for r in (d.get("pnl") or [])}
    bs_rows = {r["line_item"]: r for r in (d.get("balance_sheet") or [])}

    sales = _latest_year_val(pnl_rows, "Sales") or 0
    op = _latest_year_val(pnl_rows, "Operating Profit") or 0
    np_ = _latest_year_val(pnl_rows, "Net Profit") or 0
    opm_pct = round(op / sales * 100, 2) if sales else None
    npm_pct = round(np_ / sales * 100, 2) if sales else None
    eps = _latest_year_val(pnl_rows, "EPS in Rs")

    borrowings = _latest_year_val(bs_rows, "Borrowings") or 0
    equity = (_latest_year_val(bs_rows, "Equity Capital") or 0) + (_latest_year_val(bs_rows, "Reserves") or 0)
    debt_to_equity = round(borrowings / equity, 2) if equity else None

    # Last 8 quarters from quarterly_results table
    q_rows = d.get("quarters") or []
    if q_rows:
        all_cols = [k for k in q_rows[0] if k != "line_item"]
        q_cols = all_cols[-8:]
        quarterly_results = [{"line_item": r["line_item"], **{c: r.get(c) for c in q_cols}} for r in q_rows]
    else:
        quarterly_results = []

    # Last 5 years P&L
    if pnl_rows:
        sample = next(iter(pnl_rows.values()))
        yr_cols = sorted([k for k in sample if k.startswith("Mar")], reverse=True)[:5]
        pnl_annual = [{"line_item": r["line_item"], **{c: r.get(c) for c in yr_cols}}
                      for r in (d.get("pnl") or [])]
    else:
        pnl_annual = []

    return {
        "opm_pct": opm_pct,
        "npm_pct": npm_pct,
        "eps": eps,
        "debt_to_equity": debt_to_equity,
        "key_points": stock.get("key_points"),
        "shareholding_quarterly": stock.get("shareholding_quarterly"),
        "annual_reports": stock.get("annual_reports"),
        "credit_ratings": stock.get("credit_ratings"),
        "quarterly_results": quarterly_results,
        "pnl_annual": pnl_annual,
    }


def _fetch_from_api(symbol: str) -> dict:
    """Call yashsarawgi.me API and return parsed data dict."""
    r = _req.get(
        FUNDAMENTALS_BASE_URL,
        params={"symbol": symbol.upper(), "view": "consolidated"},
        headers={"x-api-key": FUNDAMENTALS_API_KEY},
        timeout=12,
    )
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found in fundamentals API")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Fundamentals API returned {r.status_code}")

    data = r.json()
    if not data.get("success"):
        raise HTTPException(status_code=502, detail="Fundamentals API returned success=false")

    ref = data.get("ref") or {}
    stock = data.get("stock") or {}
    ratios = stock.get("top_ratios") or ref.get("overview") or {}
    industry_cls = stock.get("industry_classification") or {}

    high_low_raw = ratios.get("High / Low", "")
    w52_high, w52_low = _parse_52w(high_low_raw)

    financials = _extract_financials(stock)

    return {
        "symbol": symbol.upper(),
        "company_name": stock.get("company_name") or ref.get("display_name"),
        "pe_ratio": _parse_float(ref.get("pe") or ratios.get("Stock P/E")),
        "pb_ratio": None,
        "roe": _parse_float(ref.get("roe") or ratios.get("ROE")),
        "roce": _parse_float(ref.get("roce") or ratios.get("ROCE")),
        "market_cap": _parse_float(ref.get("market_cap") or ratios.get("Market Cap")),
        "current_price": _parse_float(ref.get("current_price") or ratios.get("Current Price")),
        "book_value": _parse_float(ratios.get("Book Value")),
        "dividend_yield": _parse_float(ratios.get("Dividend Yield")),
        "face_value": _parse_float(ratios.get("Face Value")),
        "high_low_52w": high_low_raw,
        "week52_high": w52_high,
        "week52_low": w52_low,
        "about": stock.get("about"),
        "industry": (industry_cls.get("industry") or {}).get("name"),
        "sector": (industry_cls.get("sector") or {}).get("name"),
        "peer_comparison": stock.get("peer_comparison"),
        "raw_ref": ref,
        **financials,
    }


def _get_or_refresh(symbol: str, force: bool = False) -> dict:
    from app.db.session import SessionLocal
    from app.db.models_fundamentals import FundamentalsCache

    db = SessionLocal()
    try:
        row = db.query(FundamentalsCache).filter(FundamentalsCache.symbol == symbol.upper()).first()
        cutoff = datetime.utcnow() - timedelta(days=CACHE_TTL_DAYS)
        cache_hit = row and not force and row.cached_at > cutoff

        if cache_hit:
            logger.debug("fundamentals: cache hit for %s (age %s days)", symbol,
                         (datetime.utcnow() - row.cached_at).days)
            return _row_to_dict(row, from_cache=True)

        # Fetch fresh data
        parsed = _fetch_from_api(symbol)

        if row:
            for k, v in parsed.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            row.cached_at = datetime.utcnow()
        else:
            row = FundamentalsCache(**{k: v for k, v in parsed.items() if k != "symbol"},
                                    symbol=symbol.upper(),
                                    cached_at=datetime.utcnow())
            db.add(row)

        db.commit()
        db.refresh(row)
        logger.info("fundamentals: cached fresh data for %s", symbol)
        return _row_to_dict(row, from_cache=False)
    finally:
        db.close()


def _row_to_dict(row: Any, from_cache: bool) -> dict:
    return {
        "symbol": row.symbol,
        "company_name": row.company_name,
        "pe_ratio": row.pe_ratio,
        "pb_ratio": row.pb_ratio,
        "roe": row.roe,
        "roce": row.roce,
        "market_cap": row.market_cap,
        "current_price": row.current_price,
        "book_value": row.book_value,
        "dividend_yield": row.dividend_yield,
        "face_value": row.face_value,
        "high_low_52w": row.high_low_52w,
        "week52_high": row.week52_high,
        "week52_low": row.week52_low,
        "about": row.about,
        "industry": row.industry,
        "sector": row.sector,
        "peer_comparison": row.peer_comparison,
        "opm_pct": row.opm_pct,
        "npm_pct": row.npm_pct,
        "eps": row.eps,
        "debt_to_equity": row.debt_to_equity,
        "key_points": row.key_points,
        "shareholding_quarterly": row.shareholding_quarterly,
        "annual_reports": row.annual_reports,
        "credit_ratings": row.credit_ratings,
        "quarterly_results": row.quarterly_results,
        "pnl_annual": row.pnl_annual,
        "cached_at": row.cached_at.isoformat() if row.cached_at else None,
        "from_cache": from_cache,
        "cache_ttl_days": CACHE_TTL_DAYS,
    }


@router.get("/{symbol}")
def get_fundamentals(symbol: str):
    """Fetch fundamentals for a symbol. Returns cached data if < 90 days old."""
    return _get_or_refresh(symbol.upper().strip())


@router.post("/{symbol}/refresh")
def refresh_fundamentals(symbol: str):
    """Force-refresh fundamentals cache for a symbol (e.g. after quarterly results)."""
    return _get_or_refresh(symbol.upper().strip(), force=True)


# ── Public helper used by trading_agents ────────────────────────────────────

def get_fundamentals_data(symbol: str) -> dict:
    """
    Called by trading_agents._get_fundamental_data().
    Returns a flat dict with all available metrics.
    Never raises — returns empty dict on failure.
    """
    try:
        return _get_or_refresh(symbol.upper().strip())
    except Exception as e:
        logger.warning("fundamentals: get_fundamentals_data failed for %s: %s", symbol, e)
        return {}
