"""
INDstocks instruments sync service.

Fetches equity, fno, and index instrument CSVs from INDstocks API
and persists them into the indstocks_instruments table.

This replaces the hardcoded _INDEX_FALLBACK_SCRIP map in market_data.py
with a live, self-updating contract that never needs manual edits.
"""

import csv
import io
import logging
import time
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.indstocks.com"

# Aliases: what callers pass → what the index CSV SEGMENT column contains (uppercased)
_INDEX_ALIASES = {
    "NIFTY":     "NIFTY 50",
    "BANKNIFTY": "BANK NIFTY",
    "FINNIFTY":  "NIFTYFINSRV25 50",
    "NIFTYVIX":  "INDIA VIX",
}


def sync_instruments(force: bool = False) -> int:
    """
    Fetch all 3 INDstocks instrument CSVs and upsert into indstocks_instruments table.

    Returns total rows upserted. Skips sync if table was updated within last 12 hours
    unless force=True.
    """
    from app.db.session import SessionLocal
    from app.db.models_instruments import IndstocksInstrument
    from app.core.broker.indstocks.market_data import _access_token, _rate_limiter
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    from app.db.session import engine

    db = SessionLocal()
    try:
        # Skip if recently synced (unless forced)
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
                    logger.info("INDstocks instruments: skipping sync (synced %.1fh ago, %d rows in DB)", age_hours, count)
                    return count

        token = _access_token()
        headers = {"Authorization": token}
        is_postgres = engine.dialect.name == "postgresql"

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
                logger.warning("INDstocks instruments sync failed for source=%s: %s", source, exc)
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
                else:
                    sym = (row.get("TRADING_SYMBOL") or "").strip().upper()

                if not sym:
                    continue

                # NSE always wins over BSE for dual-listed stocks
                if sym not in rows_by_sym or exch == "NSE":
                    rows_by_sym[sym] = {
                        "symbol":     sym,
                        "scrip_code": f"{exch}_{sid}",
                        "exchange":   exch,
                        "source":     source,
                    }

            rows = list(rows_by_sym.values())

            if not rows:
                continue

            # Also insert short aliases for index source (NIFTY → NIFTY 50 entry)
            if source == "index":
                sym_to_scrip = {r["symbol"]: r["scrip_code"] for r in rows}
                for alias, full_name in _INDEX_ALIASES.items():
                    scrip = sym_to_scrip.get(full_name)
                    if scrip:
                        rows.append({
                            "symbol":     alias,
                            "scrip_code": scrip,
                            "exchange":   "NSE",
                            "source":     "index",
                        })

            # Upsert: update scrip_code + synced_at on conflict
            if is_postgres:
                stmt = pg_insert(IndstocksInstrument).values(rows)
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_instrument_symbol_source",
                    set_={"scrip_code": stmt.excluded.scrip_code, "synced_at": stmt.excluded.synced_at},
                )
            else:
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

        logger.info("INDstocks instruments sync complete: %d total rows upserted", total_upserted)
        return total_upserted

    except Exception as exc:
        logger.error("INDstocks instruments sync error: %s", exc)
        db.rollback()
        return 0
    finally:
        db.close()


def get_scrip_code_from_db(symbol: str) -> str | None:
    """
    Look up scrip code from DB. Returns None if not found.
    Priority: NSE equity > NSE index > NSE fno > any exchange.
    """
    from app.db.session import SessionLocal
    from app.db.models_instruments import IndstocksInstrument

    sym = symbol.upper().strip()
    db = SessionLocal()
    try:
        # Prefer NSE, then any exchange; prefer equity > index > fno
        for source in ("equity", "index", "fno"):
            # Try NSE first
            row = db.query(IndstocksInstrument.scrip_code).filter(
                IndstocksInstrument.symbol == sym,
                IndstocksInstrument.source == source,
                IndstocksInstrument.exchange == "NSE",
            ).first()
            if row:
                return row[0]
            # Fall back to any exchange for this source
            row = db.query(IndstocksInstrument.scrip_code).filter(
                IndstocksInstrument.symbol == sym,
                IndstocksInstrument.source == source,
            ).first()
            if row:
                return row[0]
        return None
    finally:
        db.close()
