"""
migrate_pg_to_sqlite.py
-----------------------
One-time migration: local Docker PostgreSQL -> fresh SQLite (fasttrade_new.db)

Run from backend/:
    python migrate_pg_to_sqlite.py

Output: backend/fasttrade_new.db
After verifying, rename it to trading.db.
"""

import sqlite3
import sys
import time
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

PG_DSN = "postgresql://fasttrade:your_new_password@localhost:5432/fasttrade"
SQLITE_PATH = "fasttrade_new.db"

# ---------------------------------------------------------------------------
# Tables and their migration strategy
# ---------------------------------------------------------------------------
# "skip"        — don't migrate (sessions, logs, encrypted secrets — recreate fresh)
# "migrate"     — full copy
# "migrate_big" — copy in batches (candle tables with millions of rows)

TABLE_PLAN = {
    # ── Candles (big) ──────────────────────────────────────────────────────
    "candles_daily":                "migrate_big",
    "candles_weekly":               "migrate_big",
    "candles_1h":                   "migrate_big",
    "candles_15m":                  "migrate_big",
    "candles_5m":                   "migrate_big",
    "candles_1m":                   "migrate_big",
    "option_historical_candles":    "migrate_big",

    # ── Core data ──────────────────────────────────────────────────────────
    "finance_transactions":         "migrate",
    "fii_dii_daily":                "migrate",
    "vix_historic":                 "migrate",
    "watchlists":                   "migrate",
    "watchlist_alerts":             "migrate",
    "strategy_configs":             "migrate",
    "strategy_runs":                "migrate",
    "condition_strategies":         "migrate",
    "condition_strategy_backtests": "migrate",
    "risk_limits":                  "migrate",
    "auto_trader_config":           "migrate",
    "auto_trader_log":              "migrate",
    "signal_outcomes":              "migrate",
    "scanner_signal_history":       "migrate",
    "ai_decisions":                 "migrate",
    "ai_usage_logs":                "migrate",
    "notifications":                "migrate",
    "nse_snapshots":                "migrate",
    "fundamentals_cache":           "migrate",
    "stock_holdings":               "migrate",
    "trade_journal":                "migrate",
    "trade_costs":                  "migrate",
    "brokerage_config":             "migrate",
    "budgets":                      "migrate",
    "expense_forecasts":            "migrate",
    "recurring_transactions":       "migrate",
    "savings_goals":                "migrate",
    "bill_reminders":               "migrate",
    "twitter_accounts":             "migrate",
    "twitter_sentiment":            "migrate",
    "twitter_symbol_sentiment":     "migrate",
    "twitter_alerts":               "migrate",
    "indstocks_instruments":        "migrate_big",
    "ml_scan_results":              "migrate",
    "ml_training_runs":             "migrate",
    "execution_intents":            "migrate",
    "system_control":               "migrate",
    "alert_rules":                  "migrate",
    "symbols":                      "migrate",
    "market_data":                  "migrate",
    "backtest_results":             "migrate",
    "backtest_trades":              "migrate",
    "daily_capital":                "migrate",
    "currency_exchanges":           "migrate",
    "scalp_trades":                 "migrate",
    "alexa_memories":               "migrate",
    "alexa_interaction_logs":       "migrate",

    # ── Skip — recreate fresh (encrypted tokens, sessions, auth) ──────────
    "users":                        "skip",
    "broker_credentials":           "skip",
    "user_settings":                "skip",
    "notification_settings":        "skip",
    "indmoney_sessions":            "skip",
    "zerodha_sessions":             "skip",
}

BATCH_SIZE = 50_000


def pg_connect():
    return psycopg2.connect(PG_DSN, cursor_factory=psycopg2.extras.RealDictCursor)


def get_pg_tables(pg_cur):
    pg_cur.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
    )
    return [r["tablename"] for r in pg_cur.fetchall()]


def get_pg_columns(pg_cur, table):
    pg_cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name=%s ORDER BY ordinal_position",
        (table,),
    )
    return [r["column_name"] for r in pg_cur.fetchall()]


def get_pg_count(pg_cur, table):
    pg_cur.execute(f'SELECT COUNT(*) AS n FROM "{table}"')
    return pg_cur.fetchone()["n"]


def create_sqlite_table(sl_cur, pg_cur, table):
    """Create table in SQLite mirroring Postgres schema (types simplified)."""
    pg_cur.execute(
        "SELECT column_name, data_type, is_nullable "
        "FROM information_schema.columns "
        "WHERE table_name=%s ORDER BY ordinal_position",
        (table,),
    )
    cols = pg_cur.fetchall()

    type_map = {
        "integer": "INTEGER",
        "bigint": "INTEGER",
        "smallint": "INTEGER",
        "boolean": "INTEGER",          # SQLite has no BOOLEAN
        "double precision": "REAL",
        "real": "REAL",
        "numeric": "REAL",
        "character varying": "TEXT",
        "text": "TEXT",
        "date": "TEXT",
        "timestamp with time zone": "TEXT",
        "timestamp without time zone": "TEXT",
        "json": "TEXT",
        "jsonb": "TEXT",
    }

    col_defs = []
    for c in cols:
        sl_type = type_map.get(c["data_type"], "TEXT")
        nullable = "" if c["is_nullable"] == "YES" else " NOT NULL"
        if c["column_name"] == "id":
            col_defs.append("id INTEGER PRIMARY KEY")
        else:
            col_defs.append(f'"{c["column_name"]}" {sl_type}')

    ddl = f'CREATE TABLE IF NOT EXISTS "{table}" ({", ".join(col_defs)})'
    sl_cur.execute(ddl)


def coerce_row(row: dict) -> dict:
    """Convert Postgres-specific types to SQLite-safe values."""
    import json
    out = {}
    for k, v in row.items():
        if isinstance(v, bool):
            out[k] = 1 if v else 0
        elif isinstance(v, datetime):
            if v.tzinfo is not None:
                v = v.astimezone(timezone.utc).replace(tzinfo=None)
            out[k] = v.isoformat(sep=" ")
        elif isinstance(v, (dict, list)):
            out[k] = json.dumps(v)
        elif v is None:
            out[k] = None
        else:
            out[k] = v
    return out


def migrate_table(pg_conn, sl_conn, table, big=False):
    pg_cur = pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    sl_cur = sl_conn.cursor()

    total = get_pg_count(pg_cur, table)
    if total == 0:
        print(f"  {table}: 0 rows — skipping")
        return

    cols = get_pg_columns(pg_cur, table)
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(f'"{c}"' for c in cols)
    insert_sql = f'INSERT OR IGNORE INTO "{table}" ({col_names}) VALUES ({placeholders})'

    if not big:
        pg_cur.execute(f'SELECT * FROM "{table}"')
        rows = pg_cur.fetchall()
        batch = [tuple(coerce_row(dict(r)).values()) for r in rows]
        sl_cur.executemany(insert_sql, batch)
        sl_conn.commit()
        print(f"  {table}: {len(batch)} rows migrated")
        return

    # Batched for large tables
    offset = 0
    migrated = 0
    t0 = time.time()
    while True:
        pg_cur.execute(f'SELECT * FROM "{table}" ORDER BY id LIMIT %s OFFSET %s', (BATCH_SIZE, offset))
        rows = pg_cur.fetchall()
        if not rows:
            break
        batch = [tuple(coerce_row(dict(r)).values()) for r in rows]
        sl_cur.executemany(insert_sql, batch)
        sl_conn.commit()
        migrated += len(rows)
        elapsed = time.time() - t0
        pct = migrated / total * 100
        print(f"  {table}: {migrated:,}/{total:,} ({pct:.1f}%) — {elapsed:.0f}s", end="\r")
        offset += BATCH_SIZE
        if len(rows) < BATCH_SIZE:
            break

    print(f"  {table}: {migrated:,} rows migrated ({time.time()-t0:.0f}s)          ")


def main():
    print(f"Connecting to Postgres...")
    try:
        pg_conn = pg_connect()
    except Exception as e:
        print(f"ERROR: Cannot connect to Postgres: {e}")
        sys.exit(1)

    pg_cur = pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    pg_tables = get_pg_tables(pg_cur)
    print(f"Found {len(pg_tables)} tables in Postgres")

    print(f"\nCreating SQLite: {SQLITE_PATH}")
    sl_conn = sqlite3.connect(SQLITE_PATH)
    sl_conn.execute("PRAGMA journal_mode=WAL")
    sl_conn.execute("PRAGMA synchronous=NORMAL")
    sl_conn.execute("PRAGMA cache_size=-64000")  # 64MB cache during migration
    sl_conn.execute("PRAGMA temp_store=MEMORY")

    # Create all tables first
    print("\nCreating tables in SQLite...")
    sl_cur = sl_conn.cursor()
    for table in pg_tables:
        plan = TABLE_PLAN.get(table, "migrate")
        if plan == "skip":
            print(f"  {table}: SKIPPED (will be recreated fresh by app)")
            continue
        create_sqlite_table(sl_cur, pg_cur, table)
        print(f"  {table}: table created")
    sl_conn.commit()

    # Migrate data
    print("\nMigrating data...")
    total_tables = sum(1 for t in pg_tables if TABLE_PLAN.get(t, "migrate") != "skip")
    done = 0
    for table in pg_tables:
        plan = TABLE_PLAN.get(table, "migrate")
        if plan == "skip":
            continue
        done += 1
        print(f"\n[{done}/{total_tables}] {table}")
        try:
            migrate_table(pg_conn, sl_conn, table, big=(plan == "migrate_big"))
        except Exception as e:
            print(f"  ERROR migrating {table}: {e}")

    sl_conn.close()

    # Retry tables that failed due to JSON columns
    RETRY_TABLES = [
        "ai_decisions", "alexa_interaction_logs", "auto_trader_config",
        "auto_trader_log", "condition_strategies", "condition_strategy_backtests",
        "execution_intents", "fundamentals_cache", "ml_training_runs",
        "notifications", "nse_snapshots", "risk_limits", "strategy_configs",
        "strategy_runs", "trade_journal", "twitter_sentiment", "watchlists",
    ]
    print("\nRetrying failed tables (JSON columns)...")
    sl_conn = sqlite3.connect(SQLITE_PATH)
    sl_conn.execute("PRAGMA journal_mode=WAL")
    sl_conn.execute("PRAGMA synchronous=NORMAL")
    for table in RETRY_TABLES:
        print(f"  [{table}]")
        try:
            migrate_table(pg_conn, sl_conn, table, big=False)
        except Exception as e:
            print(f"  ERROR: {e}")
    sl_conn.close()
    pg_conn.close()

    print(f"\n✅ Migration complete → {SQLITE_PATH}")
    print("Next steps:")
    print("  1. Verify row counts below match Postgres")
    print("  2. Rename: move trading.db trading_old.db && move fasttrade_new.db trading.db")

    # Quick verification
    print("\nVerification (SQLite row counts):")
    sl_conn = sqlite3.connect(SQLITE_PATH)
    sl_cur = sl_conn.cursor()
    sl_cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    for (t,) in sl_cur.fetchall():
        sl_cur.execute(f'SELECT COUNT(*) FROM "{t}"')
        print(f"  {t}: {sl_cur.fetchone()[0]:,}")
    sl_conn.close()


if __name__ == "__main__":
    main()
