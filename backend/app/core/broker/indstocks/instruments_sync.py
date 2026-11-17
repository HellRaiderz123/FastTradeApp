"""
INDstocks instruments sync service.

Fetches equity, fno, and index instrument CSVs from INDstocks API
and persists them into the indstocks_instruments table.

Architecture (OpenAlgo-style):
  1. sync_instruments()  — downloads contracts from API → writes to DB (run once on startup + daily)
  2. load_cache_from_db() — loads DB rows into the in-memory _sym_cache (instant, no API call)
  3. All LTP resolution uses the in-memory cache populated from DB
  API is NEVER called per-LTP-request — only during scheduled sync.
"""

import csv
import io
import logging
import time
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.indstocks.com"

# Underlying name aliases: CSV name → short name used in lookup keys
_UND_ALIASES = {
    "NIFTY 50":          "NIFTY",
    "NIFTY50":           "NIFTY",
    "BANK NIFTY":        "BANKNIFTY",
    "NIFTY BANK":        "BANKNIFTY",
    "NIFTYFINSRV25 50":  "FINNIFTY",
    "NIFTY FIN SERVICE": "FINNIFTY",
}

# Index aliases: short caller name → CSV SEGMENT column value
_INDEX_ALIASES = {
    "NIFTY":     "NIFTY 50",
    "BANKNIFTY": "BANK NIFTY",
    "FINNIFTY":  "NIFTYFINSRV25 50",
    "NIFTYVIX":  "INDIA VIX",
}


def load_cache_from_db() -> int:
    """
    Load all rows from indstocks_instruments DB table into the in-memory _sym_cache.
    This is the PRIMARY cache-warm path — instant, no API call.
    Returns number of rows loaded.
    """
    from app.db.session import SessionLocal
    from app.db.models_instruments import IndstocksInstrument
    from app.core.broker.indstocks.market_data import _sym_cache, _cache_loaded_at
    import app.core.broker.indstocks.market_data as _md
    import time as _time

    db = SessionLocal()
    try:
        rows = db.query(
            IndstocksInstrument.symbol,
            IndstocksInstrument.scrip_code,
        ).all()

        if not rows:
            logger.info("INDstocks DB instruments table is empty — sync needed")
            return 0

        _md._sym_cache.clear()
        for symbol, scrip_code in rows:
            _md._sym_cache[symbol] = scrip_code
        _md._cache_loaded_at = _time.time()

        logger.info("INDstocks instruments cache loaded from DB: %d symbols", len(_md._sym_cache))
        return len(_md._sym_cache)
    except Exception as exc:
        logger.error("INDstocks load_cache_from_db failed: %s", exc)
        return 0
    finally:
        db.close()


def sync_instruments(force: bool = False) -> int:
    """
    Download all 3 INDstocks instrument CSVs from API and upsert into DB.
    After upsert, reloads the in-memory cache from DB.

    Skips API download if DB was synced within last 12 hours (unless force=True).
    Returns total rows in DB after sync.
    """
    from app.db.session import SessionLocal
    from app.db.models_instruments import IndstocksInstrument
    from app.core.broker.indstocks.market_data import _access_token, _rate_limiter
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    db = SessionLocal()
    try:
        # Skip API download if recently synced
        if not force:
            latest = db.query(IndstocksInstrument.synced_at).order_by(
                IndstocksInstrument.synced_at.desc()
            ).first()
            if latest and latest[0]:
                synced_at = latest[0]
                if synced_at.tzinfo:
                    from datetime import timezone
                    age_hours = (datetime.now(timezone.utc) - synced_at).total_seconds() / 3600
                else:
                    age_hours = (datetime.utcnow() - synced_at).total_seconds() / 3600
                if age_hours < 12:
                    count = db.query(IndstocksInstrument).count()
                    logger.info(
                        "INDstocks instruments: DB synced %.1fh ago (%d rows) — loading cache from DB",
                        age_hours, count,
                    )
                    load_cache_from_db()
                    return count

        token = _access_token()
        headers = {"Authorization": token}
        total_upserted = 0

        for source in ("equity", "fno", "index"):
            _rate_limiter.wait()
            try:
                resp = requests.get(
                    f"{BASE_URL}/market/instruments",
                    params={"source": source},
                    headers=headers,
                    timeout=15,
                )
                if resp.status_code == 429:
                    time.sleep(int(resp.headers.get("Retry-After", 3)))
                    continue
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("INDstocks instruments API failed for source=%s: %s", source, exc)
                continue

            rows_by_sym: dict = {}
            reader = csv.DictReader(io.StringIO(resp.text))
            for row in reader:
                exch = (row.get("EXCH") or "NSE").strip().upper()
                sid  = (row.get("SECURITY_ID") or "").strip()
                if not sid:
                    continue

                if source == "index":
                    sym = (row.get("SEGMENT") or "").strip().upper()
                    seg = "NIDX" if exch == "NSE" else ("BIDX" if exch == "BSE" else exch)
                    scrip = f"{seg}_{sid}"
                else:
                    sym = (row.get("TRADING_SYMBOL") or "").strip().upper()
                    seg = "NFO" if source == "fno" else exch
                    scrip = f"{seg}_{sid}"

                if not sym:
                    continue

                # NSE wins over BSE for dual-listed
                if sym not in rows_by_sym or exch == "NSE":
                    rows_by_sym[sym] = {
                        "symbol": sym, "scrip_code": scrip,
                        "exchange": exch, "source": source,
                    }

                if source == "fno":
                    # Store UNDERLYING|EXPIRY|STRIKE|TYPE lookup keys
                    try:
                        underlying_name = (row.get("UNDERLYING_SCRIP_NAME") or "").strip().upper()
                        strike_raw = (row.get("STRIKE_PRICE") or "").strip()
                        opt_type = (row.get("OPTION_TYPE") or "").strip().upper()
                        expiry_raw = (row.get("EXPIRY_DATE") or "").strip()
                        if underlying_name and strike_raw and opt_type and expiry_raw:
                            from datetime import datetime as _dt
                            exp_date = _dt.strptime(expiry_raw.split()[0], "%m/%d/%Y").date()
                            strike_int = int(float(strike_raw))
                            # Primary key: exact CSV underlying name
                            for und in _iter_underlying_keys(underlying_name):
                                lk = f"{und}|{exp_date}|{strike_int}|{opt_type}"
                                if lk not in rows_by_sym:
                                    rows_by_sym[lk] = {
                                        "symbol": lk, "scrip_code": scrip,
                                        "exchange": exch, "source": source,
                                    }
                    except Exception:
                        pass

            rows = list(rows_by_sym.values())
            if not rows:
                continue

            # Short aliases for index (NIFTY → NIFTY 50 scrip)
            if source == "index":
                sym_to_scrip = {r["symbol"]: r["scrip_code"] for r in rows}
                for alias, full_name in _INDEX_ALIASES.items():
                    scrip = sym_to_scrip.get(full_name)
                    if scrip and alias not in rows_by_sym:
                        rows.append({
                            "symbol": alias, "scrip_code": scrip,
                            "exchange": "NSE", "source": "index",
                        })

            stmt = sqlite_insert(IndstocksInstrument).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "source"],
                set_={"scrip_code": stmt.excluded.scrip_code, "synced_at": stmt.excluded.synced_at},
            )
            result = db.execute(stmt)
            db.commit()
            upserted = result.rowcount if result.rowcount >= 0 else len(rows)
            total_upserted += upserted
            logger.info("INDstocks instruments synced source=%s: %d rows", source, upserted)

        logger.info("INDstocks instruments sync complete: %d rows upserted", total_upserted)

    except Exception as exc:
        logger.error("INDstocks instruments sync error: %s", exc)
        db.rollback()
        return 0
    finally:
        db.close()

    # Reload in-memory cache from DB after successful sync
    return load_cache_from_db()


def _iter_underlying_keys(underlying_name: str):
    """Yield the CSV underlying name + its short alias (if any)."""
    yield underlying_name
    alias = _UND_ALIASES.get(underlying_name)
    if alias:
        yield alias


def get_scrip_code_from_db(symbol: str) -> str | None:
    """
    Look up scrip code from DB.
    Priority: trading symbol direct > UNDERLYING|EXPIRY|STRIKE|TYPE key.
    """
    from app.db.session import SessionLocal
    from app.db.models_instruments import IndstocksInstrument

    sym = symbol.upper().strip()
    db = SessionLocal()
    try:
        # F&O lookup keys contain pipes
        if "|" in sym:
            row = db.query(IndstocksInstrument.scrip_code).filter(
                IndstocksInstrument.symbol == sym,
            ).first()
            return row[0] if row else None

        source_order = (
            ("index", "equity", "fno") if sym in _INDEX_ALIASES or " " in sym
            else ("equity", "index", "fno")
        )
        for source in source_order:
            if source == "index":
                row = db.query(IndstocksInstrument.scrip_code).filter(
                    IndstocksInstrument.symbol == sym,
                    IndstocksInstrument.source == source,
                ).first()
            else:
                row = db.query(IndstocksInstrument.scrip_code).filter(
                    IndstocksInstrument.symbol == sym,
                    IndstocksInstrument.source == source,
                    IndstocksInstrument.exchange == "NSE",
                ).first()
                if not row:
                    row = db.query(IndstocksInstrument.scrip_code).filter(
                        IndstocksInstrument.symbol == sym,
                        IndstocksInstrument.source == source,
                    ).first()
            if row:
                return row[0]
        return None
    finally:
        db.close()
