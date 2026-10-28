"""
FII/DII Data API — fetches live from NSE (same logic as MrChartist/fii-dii-data).

Cash data:  GET https://www.nseindia.com/api/fiidiiTradeReact  (needs NSE session cookie)
F&O data:   GET https://nsearchives.nseindia.com/content/nsccl/fao_participant_oi_DDMMYYYY_b.csv

In-memory cache: cash 4h TTL, F&O 4h TTL.
Falls back to GitHub raw JSON if NSE is unreachable.

Endpoints:
  GET /api/fii-dii/latest    — latest session snapshot
  GET /api/fii-dii/history   — last N days (default 60)
  GET /api/fii-dii/summary   — streaks, MTD, YTD, 20-day averages + heatmap
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import date as _date, datetime, timedelta
from typing import Any, Optional

import requests as _req
from fastapi import APIRouter, Query
from app.core.market.nse_client import nse_get
from app.db.session import SessionLocal
from app.db.models_fii_dii import FiiDiiDaily

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fii-dii", tags=["fii-dii"])

NSE_CASH   = "https://www.nseindia.com/api/fiidiiTradeReact"
FAO_BASE   = "https://nsearchives.nseindia.com/content/nsccl"
PROXY_URL  = "https://api.allorigins.win/get?url={}"
GITHUB_URL = "https://raw.githubusercontent.com/MrChartist/fii-dii-data/main/data/history.json"
CACHE_TTL_HOURS = 4

MONTH_MAP = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}

_cache: dict[str, Any] = {"data": None, "fetched_at": None}


# ── Cash data fetch ──────────────────────────────────────────────────────────

def _fetch_cash_nse() -> list[dict]:
    """Fetch today's FII/DII cash row directly from NSE (Mac UA works without session)."""
    _HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, */*",
        "Referer": "https://www.nseindia.com/reports-indices-fii-dii-trading-activity",
    }
    try:
        r = _req.get(NSE_CASH, headers=_HEADERS, timeout=25)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                logger.info("fii_dii: NSE cash fetch OK (%d rows)", len(data))
                return data
        logger.warning("fii_dii: NSE cash returned status %s", r.status_code)
    except Exception as e:
        logger.warning("fii_dii: NSE cash fetch failed: %s", e)

    # allorigins proxy fallback
    try:
        import urllib.parse, json as _json
        proxy = PROXY_URL.format(urllib.parse.quote(NSE_CASH, safe=""))
        r = _req.get(proxy, timeout=30)
        if r.status_code == 200:
            data = _json.loads(r.json().get("contents") or "null")
            if isinstance(data, list) and data:
                logger.info("fii_dii: allorigins proxy OK (%d rows)", len(data))
                return data
    except Exception as e:
        logger.warning("fii_dii: allorigins proxy failed: %s", e)

    return []


def _parse_cash_rows(raw_rows: list[dict]) -> Optional[dict]:
    """
    NSE fiidiiTradeReact returns 2 rows per day: one for DII, one for FII/FPI.
    Merge them into a single record keyed by date.
    Fields: buyValue, sellValue, netValue, category, date
    """
    def _f(v: Any) -> float:
        try:
            return float(str(v or "0").replace(",", "").strip())
        except Exception:
            return 0.0

    fii_row = next((r for r in raw_rows if "FII" in str(r.get("category", "")).upper()), None)
    dii_row = next((r for r in raw_rows if "DII" in str(r.get("category", "")).upper()), None)

    if not fii_row and not dii_row:
        return None

    ref = fii_row or dii_row
    date = str(ref.get("date") or "").strip()
    if not date:
        return None

    try:
        parsed_date = datetime.strptime(date, "%d-%b-%Y").date().isoformat()
    except Exception:
        parsed_date = date

    fii_buy  = _f(fii_row.get("buyValue"))  if fii_row else 0.0
    fii_sell = _f(fii_row.get("sellValue")) if fii_row else 0.0
    fii_net  = _f(fii_row.get("netValue"))  if fii_row else round(fii_buy - fii_sell, 2)
    dii_buy  = _f(dii_row.get("buyValue"))  if dii_row else 0.0
    dii_sell = _f(dii_row.get("sellValue")) if dii_row else 0.0
    dii_net  = _f(dii_row.get("netValue"))  if dii_row else round(dii_buy - dii_sell, 2)

    return {
        "date": date,
        "_parsed_date": parsed_date,
        "fii_buy": round(fii_buy, 2),
        "fii_sell": round(fii_sell, 2),
        "fii_net": round(fii_net, 2),
        "dii_buy": round(dii_buy, 2),
        "dii_sell": round(dii_sell, 2),
        "dii_net": round(dii_net, 2),
        "fii_idx_fut_long": None, "fii_idx_fut_short": None, "fii_idx_fut_net": None,
        "dii_idx_fut_long": None, "dii_idx_fut_short": None, "dii_idx_fut_net": None,
        "fii_stk_fut_long": None, "fii_stk_fut_short": None, "fii_stk_fut_net": None,
        "fii_idx_call_long": None, "fii_idx_call_short": None, "fii_idx_call_net": None,
        "fii_idx_put_long": None, "fii_idx_put_short": None, "fii_idx_put_net": None,
        "pcr": None,
        "sentiment_score": 50,
        "_fao_summary": None,
    }


# ── F&O data fetch ───────────────────────────────────────────────────────────

def _fetch_fao_csv(date_str: str) -> Optional[str]:
    """
    Fetch NSE F&O participant OI CSV for a given date (DD-Mon-YYYY).
    Tries _b.csv first, then plain .csv.
    """
    parts = date_str.split("-")
    if len(parts) != 3:
        return None
    day, mon, year = parts
    month_num = MONTH_MAP.get(mon)
    if not month_num:
        return None
    date_part = f"{day.zfill(2)}{month_num}{year}"

    urls = [
        f"{FAO_BASE}/fao_participant_oi_{date_part}_b.csv",
        f"{FAO_BASE}/fao_participant_oi_{date_part}.csv",
    ]
    for url in urls:
        try:
            r = nse_get(url, timeout=15)
            if r.status_code == 200 and len(r.text) > 100:
                logger.info("fii_dii: F&O CSV fetched for %s from %s", date_str, url)
                return r.text
        except Exception as e:
            logger.debug("fii_dii: F&O CSV fetch failed for %s: %s", url, e)
    return None


def _parse_fao_csv(csv_text: str) -> dict:
    """
    Parse NSE fao_participant_oi CSV by column header (not position).
    Returns {"FII": {...}, "DII": {...}}
    """
    result: dict[str, dict] = {}
    if not csv_text:
        return result
    try:
        lines = [l for l in csv_text.strip().splitlines() if l.strip() and not l.startswith(",")]
        if len(lines) < 2:
            return result

        reader = csv.DictReader(io.StringIO("\n".join(lines)))

        def _int(val: Any) -> int:
            try:
                return int(str(val or "0").replace(",", "").strip())
            except Exception:
                return 0

        for row in reader:
            client = (row.get("Client Type") or "").strip().upper()
            if "FII" in client:
                key = "FII"
            elif "DII" in client:
                key = "DII"
            else:
                continue

            result[key] = {
                "idx_fut_long":   _int(row.get("Future Index Long")),
                "idx_fut_short":  _int(row.get("Future Index Short")),
                "stk_fut_long":   _int(row.get("Future Stock Long")),
                "stk_fut_short":  _int(row.get("Future Stock Short")),
                "idx_call_long":  _int(row.get("Option Index Call Long")),
                "idx_call_short": _int(row.get("Option Index Call Short")),
                "idx_put_long":   _int(row.get("Option Index Put Long")),
                "idx_put_short":  _int(row.get("Option Index Put Short")),
            }
    except Exception as e:
        logger.warning("fii_dii: F&O CSV parse error: %s", e)
    return result


def _apply_fao(row: dict, fao: dict) -> None:
    """Merge parsed F&O data into a cash row in-place. Recomputes PCR + sentiment."""
    fii = fao.get("FII")
    dii = fao.get("DII")

    if fii:
        row["fii_idx_fut_long"]  = fii["idx_fut_long"]
        row["fii_idx_fut_short"] = fii["idx_fut_short"]
        row["fii_idx_fut_net"]   = fii["idx_fut_long"] - fii["idx_fut_short"]
        row["fii_stk_fut_long"]  = fii["stk_fut_long"]
        row["fii_stk_fut_short"] = fii["stk_fut_short"]
        row["fii_stk_fut_net"]   = fii["stk_fut_long"] - fii["stk_fut_short"]
        row["fii_idx_call_long"]  = fii["idx_call_long"]
        row["fii_idx_call_short"] = fii["idx_call_short"]
        row["fii_idx_call_net"]   = fii["idx_call_long"] - fii["idx_call_short"]
        row["fii_idx_put_long"]   = fii["idx_put_long"]
        row["fii_idx_put_short"]  = fii["idx_put_short"]
        row["fii_idx_put_net"]    = fii["idx_put_long"] - fii["idx_put_short"]

        # PCR = put_short / call_short (open interest ratio)
        row["pcr"] = (
            round(fii["idx_put_short"] / fii["idx_call_short"], 2)
            if fii["idx_call_short"] > 0 else 1.0
        )

        # Sentiment score (same formula as MrChartist repo)
        sentiment = 50.0
        sentiment += max(-15, min(15, (row.get("fii_net") or 0) / 500))
        sentiment += max(-15, min(15, row["fii_idx_fut_net"] / 10000))
        pcr = row["pcr"] or 1.0
        if pcr > 1.3:   sentiment -= 8
        elif pcr > 1.1: sentiment -= 4
        if pcr < 0.7:   sentiment += 8
        elif pcr < 0.9: sentiment += 4
        row["sentiment_score"] = round(min(100, max(5, sentiment)), 1)

        row["_fao_summary"] = {
            "sentiment": "Bullish" if row["sentiment_score"] > 60 else ("Bearish" if row["sentiment_score"] < 40 else "Neutral"),
            "pcr": row["pcr"],
            "fii_fut_net": row["fii_idx_fut_net"],
            "fii_call_net": row["fii_idx_call_net"],
            "fii_put_net": row["fii_idx_put_net"],
        }

    if dii:
        row["dii_idx_fut_long"]  = dii["idx_fut_long"]
        row["dii_idx_fut_short"] = dii["idx_fut_short"]
        row["dii_idx_fut_net"]   = dii["idx_fut_long"] - dii["idx_fut_short"]


# ── GitHub fallback ──────────────────────────────────────────────────────────

def _fetch_github_fallback() -> list[dict]:
    try:
        r = _req.get(GITHUB_URL, timeout=15)
        r.raise_for_status()
        raw = r.json()
        today = datetime.utcnow().date()
        valid = []
        for row in raw:
            try:
                d = datetime.strptime(row["date"], "%d-%b-%Y").date()
                if d <= today:
                    valid.append({**row, "_parsed_date": d.isoformat()})
            except Exception:
                pass
        valid.sort(key=lambda x: x["_parsed_date"])
        logger.info("fii_dii: GitHub fallback loaded %d records", len(valid))
        return valid
    except Exception as e:
        logger.warning("fii_dii: GitHub fallback failed: %s", e)
        return []


# ── DB persistence helpers ───────────────────────────────────────────────────

def _row_to_dict(rec: FiiDiiDaily) -> dict:
    """Convert a DB row to the same dict shape used throughout this module."""
    d = rec.date.strftime("%d-%b-%Y")  # e.g. "01-Jan-2025"
    return {
        "date": d,
        "_parsed_date": rec.date.isoformat(),
        "fii_buy":  rec.fii_buy,  "fii_sell": rec.fii_sell,  "fii_net": rec.fii_net,
        "dii_buy":  rec.dii_buy,  "dii_sell": rec.dii_sell,  "dii_net": rec.dii_net,
        "fii_idx_fut_long":   rec.fii_idx_fut_long,
        "fii_idx_fut_short":  rec.fii_idx_fut_short,
        "fii_idx_fut_net":    rec.fii_idx_fut_net,
        "fii_stk_fut_long":   rec.fii_stk_fut_long,
        "fii_stk_fut_short":  rec.fii_stk_fut_short,
        "fii_stk_fut_net":    rec.fii_stk_fut_net,
        "fii_idx_call_long":  rec.fii_idx_call_long,
        "fii_idx_call_short": rec.fii_idx_call_short,
        "fii_idx_call_net":   rec.fii_idx_call_net,
        "fii_idx_put_long":   rec.fii_idx_put_long,
        "fii_idx_put_short":  rec.fii_idx_put_short,
        "fii_idx_put_net":    rec.fii_idx_put_net,
        "dii_idx_fut_long":   rec.dii_idx_fut_long,
        "dii_idx_fut_short":  rec.dii_idx_fut_short,
        "dii_idx_fut_net":    rec.dii_idx_fut_net,
        "pcr":             rec.pcr,
        "sentiment_score": rec.sentiment_score,
        "_fao_summary": None,
    }


def _upsert_row(db, row: dict) -> None:
    """Insert or update a single FII/DII row in the DB."""
    try:
        trade_date = _date.fromisoformat(row["_parsed_date"])
    except Exception:
        return
    rec = db.query(FiiDiiDaily).filter(FiiDiiDaily.date == trade_date).first()
    fields = {
        "fii_buy": row.get("fii_buy"),   "fii_sell": row.get("fii_sell"),  "fii_net": row.get("fii_net"),
        "dii_buy": row.get("dii_buy"),   "dii_sell": row.get("dii_sell"),  "dii_net": row.get("dii_net"),
        "fii_idx_fut_long":   row.get("fii_idx_fut_long"),
        "fii_idx_fut_short":  row.get("fii_idx_fut_short"),
        "fii_idx_fut_net":    row.get("fii_idx_fut_net"),
        "fii_stk_fut_long":   row.get("fii_stk_fut_long"),
        "fii_stk_fut_short":  row.get("fii_stk_fut_short"),
        "fii_stk_fut_net":    row.get("fii_stk_fut_net"),
        "fii_idx_call_long":  row.get("fii_idx_call_long"),
        "fii_idx_call_short": row.get("fii_idx_call_short"),
        "fii_idx_call_net":   row.get("fii_idx_call_net"),
        "fii_idx_put_long":   row.get("fii_idx_put_long"),
        "fii_idx_put_short":  row.get("fii_idx_put_short"),
        "fii_idx_put_net":    row.get("fii_idx_put_net"),
        "dii_idx_fut_long":   row.get("dii_idx_fut_long"),
        "dii_idx_fut_short":  row.get("dii_idx_fut_short"),
        "dii_idx_fut_net":    row.get("dii_idx_fut_net"),
        "pcr":             row.get("pcr"),
        "sentiment_score": row.get("sentiment_score"),
    }
    if rec:
        for k, v in fields.items():
            if v is not None:
                setattr(rec, k, v)
    else:
        db.add(FiiDiiDaily(date=trade_date, **{k: v for k, v in fields.items() if v is not None}))


def _load_from_db() -> list[dict]:
    """Load all stored FII/DII rows from DB, sorted by date."""
    try:
        db = SessionLocal()
        try:
            rows = db.query(FiiDiiDaily).order_by(FiiDiiDaily.date).all()
            return [_row_to_dict(r) for r in rows]
        finally:
            db.close()
    except Exception as e:
        logger.warning("fii_dii: DB load failed: %s", e)
        return []


def _save_to_db(history: list[dict]) -> None:
    """Upsert all rows in history into the DB."""
    try:
        db = SessionLocal()
        try:
            for row in history:
                _upsert_row(db, row)
            db.commit()
            logger.info("fii_dii: saved %d rows to DB", len(history))
        finally:
            db.close()
    except Exception as e:
        logger.warning("fii_dii: DB save failed: %s", e)


# ── Main data loader ─────────────────────────────────────────────────────────

def _get_data(force: bool = False) -> list[dict]:
    now = datetime.utcnow()
    if (
        not force
        and _cache["data"] is not None
        and _cache["fetched_at"] is not None
        and (now - _cache["fetched_at"]) < timedelta(hours=CACHE_TTL_HOURS)
    ):
        return _cache["data"]

    # 1. Load history from DB (persistent store)
    history_by_date: dict[str, dict] = {r["_parsed_date"]: r for r in _load_from_db()}

    # 2. If DB is empty, seed from GitHub fallback
    if not history_by_date:
        logger.info("fii_dii: DB empty, seeding from GitHub fallback")
        github_rows = _fetch_github_fallback()
        for r in github_rows:
            history_by_date[r["_parsed_date"]] = r
        if github_rows:
            _save_to_db(github_rows)

    # 3. Fetch today's live row from NSE and merge/replace
    raw_rows = _fetch_cash_nse()
    if raw_rows:
        today_row = _parse_cash_rows(raw_rows)
        if today_row and today_row["_parsed_date"]:
            history_by_date[today_row["_parsed_date"]] = today_row
            logger.info("fii_dii: merged NSE live row for %s", today_row["date"])

    history = sorted(history_by_date.values(), key=lambda x: x["_parsed_date"])

    if not history:
        logger.warning("fii_dii: no data from any source")
        return _cache["data"] or []

    # 4. Fetch F&O CSV for the latest 5 rows that are missing it
    fao_updated: list[dict] = []
    for row in history[-5:]:
        if row.get("fii_idx_fut_long") not in (None, 0):
            continue
        csv_text = _fetch_fao_csv(row["date"])
        if csv_text:
            fao = _parse_fao_csv(csv_text)
            if fao:
                _apply_fao(row, fao)
                fao_updated.append(row)
                logger.info("fii_dii: F&O applied for %s", row["date"])

    # 5. Persist today's row + any F&O-enriched rows to DB
    rows_to_save = []
    if raw_rows and history:
        rows_to_save.append(history[-1])  # today
    rows_to_save.extend(fao_updated)
    if rows_to_save:
        _save_to_db(rows_to_save)

    _cache["data"] = history
    _cache["fetched_at"] = now
    logger.info("fii_dii: cache updated with %d records (latest: %s)", len(history), history[-1]["date"])
    return history


# ── Summary computation ──────────────────────────────────────────────────────

def _compute_summary(records: list[dict]) -> dict:
    if not records:
        return {}

    cash = [r for r in records if r.get("fii_net") is not None]
    if not cash:
        return {}

    last20 = cash[-20:]
    avg_fii = sum(r["fii_net"] for r in last20) / len(last20)
    avg_dii = sum(r["dii_net"] for r in last20) / len(last20)

    # Streaks
    fii_streak = dii_streak = 0
    for r in reversed(cash):
        if fii_streak == 0 or (fii_streak > 0) == (r["fii_net"] >= 0):
            fii_streak = (max(fii_streak, 0) + 1) if r["fii_net"] >= 0 else (min(fii_streak, 0) - 1)
        else:
            break
    for r in reversed(cash):
        if dii_streak == 0 or (dii_streak > 0) == (r["dii_net"] >= 0):
            dii_streak = (max(dii_streak, 0) + 1) if r["dii_net"] >= 0 else (min(dii_streak, 0) - 1)
        else:
            break

    now = datetime.utcnow()
    mtd = [r for r in cash if r["_parsed_date"][:7] == now.strftime("%Y-%m")]
    ytd = [r for r in cash if r["_parsed_date"][:4] == str(now.year)]

    latest = cash[-1]
    fii_net = latest["fii_net"]
    dii_net = latest["dii_net"]
    total = abs(fii_net) + abs(dii_net)
    fii_pct = round(abs(fii_net) / total * 100, 1) if total else 50.0
    dii_pct = round(abs(dii_net) / total * 100, 1) if total else 50.0

    # Most recent record that has real F&O data
    fno_record = next(
        (r for r in reversed(records) if r.get("fii_idx_fut_long") not in (None, 0)),
        latest
    )

    return {
        "latest_date": latest["date"],
        "fii_net": fii_net,
        "dii_net": dii_net,
        "fii_buy": latest.get("fii_buy"),
        "fii_sell": latest.get("fii_sell"),
        "dii_buy": latest.get("dii_buy"),
        "dii_sell": latest.get("dii_sell"),
        "flow_strength_fii_pct": fii_pct,
        "flow_strength_dii_pct": dii_pct,
        "fii_direction": "BUY" if fii_net >= 0 else "SELL",
        "dii_direction": "BUY" if dii_net >= 0 else "SELL",
        "fii_streak_days": fii_streak,
        "dii_streak_days": dii_streak,
        "avg_fii_20d": round(avg_fii, 2),
        "avg_dii_20d": round(avg_dii, 2),
        "mtd_fii": round(sum(r["fii_net"] for r in mtd), 2),
        "mtd_dii": round(sum(r["dii_net"] for r in mtd), 2),
        "ytd_fii": round(sum(r["fii_net"] for r in ytd), 2),
        "ytd_dii": round(sum(r["dii_net"] for r in ytd), 2),
        "sentiment_score": latest.get("sentiment_score"),
        "pcr": latest.get("pcr"),
        "fno": {
            "fii_idx_fut_long":  fno_record.get("fii_idx_fut_long"),
            "fii_idx_fut_short": fno_record.get("fii_idx_fut_short"),
            "fii_idx_fut_net":   fno_record.get("fii_idx_fut_net"),
            "dii_idx_fut_long":  fno_record.get("dii_idx_fut_long"),
            "dii_idx_fut_short": fno_record.get("dii_idx_fut_short"),
            "dii_idx_fut_net":   fno_record.get("dii_idx_fut_net"),
            "fii_stk_fut_long":  fno_record.get("fii_stk_fut_long"),
            "fii_stk_fut_short": fno_record.get("fii_stk_fut_short"),
            "fii_stk_fut_net":   fno_record.get("fii_stk_fut_net"),
            "fii_idx_call_long":  fno_record.get("fii_idx_call_long"),
            "fii_idx_call_short": fno_record.get("fii_idx_call_short"),
            "fii_idx_call_net":   fno_record.get("fii_idx_call_net"),
            "fii_idx_put_long":   fno_record.get("fii_idx_put_long"),
            "fii_idx_put_short":  fno_record.get("fii_idx_put_short"),
            "fii_idx_put_net":    fno_record.get("fii_idx_put_net"),
            "sentiment": (fno_record.get("_fao_summary") or {}).get("sentiment"),
            "fno_date": fno_record.get("date"),
        },
        "updated_at": latest.get("_updated_at") or latest.get("date"),
        "cached_at": _cache["fetched_at"].isoformat() if _cache["fetched_at"] else None,
        "source": "nse_live" if _cache.get("data") else "github_fallback",
    }


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/latest")
def get_latest():
    data = _get_data()
    return _compute_summary(data)


@router.get("/history")
def get_history(days: int = Query(60, ge=1, le=500)):
    data = _get_data()
    return {"records": data[-days:], "total": len(data[-days:])}


@router.get("/summary")
def get_summary():
    data = _get_data()
    summary = _compute_summary(data)
    last45 = data[-45:]
    summary["heatmap"] = [
        {
            "date": r["_parsed_date"],
            "fii_net": r.get("fii_net"),
            "dii_net": r.get("dii_net"),
            "sentiment_score": r.get("sentiment_score"),
        }
        for r in last45
    ]
    return summary
