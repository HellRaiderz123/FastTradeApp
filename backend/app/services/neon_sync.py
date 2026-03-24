"""
Delta sync: Local Docker PostgreSQL → Neon PostgreSQL
Runs every hour via APScheduler. Only syncs rows added/updated since last run.

Strategy per table:
  - Tables with `updated_at`  → sync WHERE updated_at > last_run
  - Tables with `created_at` only → sync WHERE created_at > last_run
  - Tables with neither       → full upsert (small tables, safe to re-sync)
"""

import logging
import os
from datetime import datetime, timezone
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

# ── State: timestamp of last successful sync (in-memory, resets on restart) ───
_last_sync_at: Optional[datetime] = None

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
    Called by the scheduler every hour.
    """
    global _last_sync_at

    since = _last_sync_at
    run_started_at = datetime.now(timezone.utc)

    logger.info(
        f"🔄 Neon delta sync started | since={since.isoformat() if since else 'FULL'}"
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
                        rows = src.execute(
                            text(f'SELECT * FROM "{table}" WHERE "{ts_col}" > :since'),
                            {"since": since},
                        ).mappings().all()
                    else:
                        rows = src.execute(
                            text(f'SELECT * FROM "{table}"')
                        ).mappings().all()

                if not rows:
                    continue

                cols = list(rows[0].keys())
                col_list = ", ".join(f'"{c}"' for c in cols)
                placeholders = ", ".join(f":{c}" for c in cols)

                # Detect primary key for ON CONFLICT
                pk_cols = [pk["name"] for pk in inspector.get_pk_constraint(table).get("constrained_columns", [])]
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

        # Update last sync timestamp only on success
        _last_sync_at = run_started_at

        logger.info(
            f"✅ Neon delta sync complete | {total_upserted} rows upserted, "
            f"{total_skipped} skipped | next run in ~1h"
        )

    except Exception as e:
        logger.error(f"❌ Neon delta sync failed: {e}", exc_info=True)
        # Don't update _last_sync_at so next run retries from same window
