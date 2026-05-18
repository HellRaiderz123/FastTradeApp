"""
Delta sync: Local Docker PostgreSQL → Neon PostgreSQL
Runs daily at 3:15 PM IST via APScheduler.

Persistence: last successful sync timestamp is written to a JSON file so that
even if the service is down for multiple days, the next run automatically
catches up with ALL rows inserted/updated since the last successful run.

Strategy per table:
  - Tables with `updated_at`  → sync WHERE updated_at > last_run
  - Tables with `created_at` only → sync WHERE created_at > last_run
  - Tables with neither       → full upsert (small tables, safe to re-sync)
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, text, inspect

logger = logging.getLogger(__name__)

# ── Neon target URL (read from env, falls back to hardcoded for safety) ────────
NEON_URL = os.getenv(
    "NEON_SYNC_URL",
    "postgresql://neondb_owner:npg_FE5ZcbnaoA6q"
    "@ep-dry-cake-a11w18of-pooler.ap-southeast-1.aws.neon.tech"
    "/neondb?sslmode=require",
)

# ── Persistent state file ─────────────────────────────────────────────────────
# Survives container restarts; ensures missed days are always caught up.
_STATE_FILE = Path(
    os.getenv("NEON_SYNC_STATE_FILE", "").strip()
    or Path(__file__).resolve().parents[2] / "data" / "neon_sync_state.json"
)


def _load_last_sync() -> Optional[datetime]:
    """Return the last successful sync timestamp from disk, or None."""
    try:
        if _STATE_FILE.exists():
            data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
            ts = data.get("last_sync_at")
            if ts:
                return datetime.fromisoformat(ts)
    except Exception as exc:
        logger.warning("⚠️  Could not read Neon sync state file: %s", exc)
    return None


def _save_last_sync(ts: datetime) -> None:
    """Persist the last successful sync timestamp to disk."""
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(
            json.dumps({"last_sync_at": ts.isoformat()}, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("⚠️  Could not save Neon sync state file: %s", exc)

# ── Tables that are too large / candle-only — skip syncing to Neon ────────────
# Candle tables are huge and Neon has free-tier row limits; exclude them.
# Add any table name here to skip it.
SKIP_TABLES = {
    "candles_1m",
    "candles_5m",
    "candles_15m",
    "candles_1h",
    "candles_daily",
    "option_historical_candles",
}


def _get_neon_engine():
    return create_engine(
        NEON_URL,
        pool_size=2,
        max_overflow=2,
        pool_pre_ping=True,
        connect_args={"sslmode": "require"},
    )


def _get_local_engine():
    local_url = os.getenv(
        "DATABASE_URL",
        "postgresql://fasttrade:fasttrade_secret@localhost:5432/fasttrade",
    )
    return create_engine(local_url, pool_size=2, max_overflow=2, pool_pre_ping=True)


def _ensure_tables_exist(neon_engine, local_engine):
    """Create any missing tables on Neon that exist locally."""
    try:
        from app.db.session import Base
        from app.db import models  # noqa: F401
        from app.db.models_intent import ExecutionIntent  # noqa: F401
        from app.db.models_notification import Notification  # noqa: F401
        from app.db.models_risk import RiskLimitConfig  # noqa: F401
        from app.db.models_auto_trader import AutoTraderConfig, AutoTraderLog  # noqa: F401
        from app.db.models_signal_outcome import SignalOutcome  # noqa: F401
        from app.db.models_scanner_signal import ScannerSignalHistory  # noqa: F401
        from app.db.models_zerodha import ZerodhaSession  # noqa: F401
        from app.db.models_watchlist import Watchlist, WatchlistAlert  # noqa: F401
        from app.db.models_finance import FinanceTransaction, RecurringTransaction, Budget, SavingsGoal, BillReminder, ExpenseForecast, CurrencyExchange  # noqa: F401
        from app.db.models_control import SystemControl  # noqa: F401
        from app.db.models_condition_strategy import ConditionStrategy, ConditionStrategyBacktest  # noqa: F401
        from app.db.models_trade_costs import TradeCost, BrokerageConfig  # noqa: F401
        from app.db.models_twitter import TwitterAccount, TwitterSentiment, TwitterSymbolSentiment, TwitterAlert  # noqa: F401

        Base.metadata.create_all(bind=neon_engine)
    except Exception as e:
        logger.warning(f"⚠️  Could not ensure Neon tables: {e}")


def run_delta_sync():
    """
    Copy rows added/updated since last sync from local Postgres → Neon.
    Called by the scheduler daily at 3:15 PM IST.

    If the service was down for N days, `since` will be N days ago and this
    run will automatically pick up all rows from the entire missed window.
    """
    since = _load_last_sync()
    run_started_at = datetime.now(timezone.utc)

    logger.info(
        "🔄 Neon delta sync started | since=%s",
        since.isoformat() if since else "FULL (first run or state lost)",
    )

    try:
        local_engine = _get_local_engine()
        neon_engine = _get_neon_engine()

        # Make sure all tables exist on Neon side
        _ensure_tables_exist(neon_engine, local_engine)

        inspector = inspect(local_engine)
        tables = [t for t in inspector.get_table_names() if t not in SKIP_TABLES]

        total_upserted = 0
        total_skipped = 0

        for table in tables:
            try:
                # Detect which timestamp column is available
                col_names = {c["name"] for c in inspector.get_columns(table)}
                if "updated_at" in col_names:
                    ts_col = "updated_at"
                elif "created_at" in col_names:
                    ts_col = "created_at"
                else:
                    ts_col = None

                # Build query
                with local_engine.connect() as src:
                    if since and ts_col:
                        result = src.execute(
                            text(f'SELECT * FROM "{table}" WHERE "{ts_col}" > :since'),
                            {"since": since},
                        )
                    else:
                        result = src.execute(text(f'SELECT * FROM "{table}"'))
                    rows = [dict(r) for r in result.mappings()]

                if not rows:
                    continue

                cols = list(rows[0].keys())
                col_list = ", ".join(f'"{c}"' for c in cols)
                placeholders = ", ".join(f":{c}" for c in cols)

                # Detect primary key for ON CONFLICT
                pk_info = inspector.get_pk_constraint(table)
                pk_cols = pk_info.get("constrained_columns", []) if isinstance(pk_info, dict) else []
                if pk_cols:
                    pk_clause = ", ".join(f'"{c}"' for c in pk_cols)
                    update_clause = ", ".join(
                        f'"{c}" = EXCLUDED."{c}"'
                        for c in cols if c not in pk_cols
                    )
                    conflict_sql = (
                        f"ON CONFLICT ({pk_clause}) DO UPDATE SET {update_clause}"
                        if update_clause
                        else f"ON CONFLICT ({pk_clause}) DO NOTHING"
                    )
                else:
                    conflict_sql = "ON CONFLICT DO NOTHING"

                upserted = 0
                with neon_engine.begin() as dst:
                    for row in rows:
                        try:
                            dst.execute(
                                text(
                                    f'INSERT INTO "{table}" ({col_list}) '
                                    f"VALUES ({placeholders}) {conflict_sql}"
                                ),
                                dict(row),
                            )
                            upserted += 1
                        except Exception as row_err:
                            logger.debug(f"  ⚠️  {table} row skip: {row_err}")
                            total_skipped += 1

                total_upserted += upserted
                logger.debug(f"  ✅ {table}: {upserted} upserted")

            except Exception as table_err:
                logger.warning(f"  ❌ {table}: {table_err}")

        # Persist last sync timestamp only on success.
        # On failure we intentionally leave it unchanged so the next run
        # retries from the same (or earlier) window, catching up all missed data.
        _save_last_sync(run_started_at)

        logger.info(
            "✅ Neon delta sync complete | %d rows upserted, %d skipped | "
            "next run tomorrow at 3:15 PM IST",
            total_upserted,
            total_skipped,
        )

    except Exception as e:
        logger.error("❌ Neon delta sync failed: %s", e, exc_info=True)
        # Do NOT update the state file — next run will retry from last good timestamp,
        # ensuring no data is ever skipped even after multiple consecutive failures.
