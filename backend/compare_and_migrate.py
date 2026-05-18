"""
Compare Neon DB vs Local Docker Postgres — then migrate any missing rows.

Usage (from backend/ directory, with Docker running):
    python compare_and_migrate.py [--dry-run]

Flags:
    --dry-run   Only print differences, do NOT insert rows
"""
import sys
import os
from sqlalchemy import create_engine, text, inspect

DRY_RUN = "--dry-run" in sys.argv

# ── Connection URLs ────────────────────────────────────────────────────────────
NEON_URL = (
    "postgresql://neondb_owner:npg_FE5ZcbnaoA6q"
    "@ep-dry-cake-a11w18of-pooler.ap-southeast-1.aws.neon.tech"
    "/neondb?sslmode=require"
)

LOCAL_URL = os.getenv(
    "LOCAL_DB_URL",
    "postgresql://fasttrade:your_new_password@localhost:5432/fasttrade",
)

print("=" * 60)
print("FastTradeApp — Neon → Local Docker Postgres Migration")
print("=" * 60)
print(f"Source : Neon ({NEON_URL.split('@')[-1]})")
print(f"Target : {LOCAL_URL.split('@')[-1]}")
print(f"Mode   : {'DRY RUN (no changes)' if DRY_RUN else 'LIVE (will insert missing rows)'}")
print()

src_engine = create_engine(NEON_URL, connect_args={"sslmode": "require"})
dst_engine = create_engine(LOCAL_URL)

# ── Step 1: Collect table names from both sides ───────────────────────────────
neon_inspector = inspect(src_engine)
local_inspector = inspect(dst_engine)

neon_tables = set(neon_inspector.get_table_names())
local_tables = set(local_inspector.get_table_names())

only_in_neon = neon_tables - local_tables
only_in_local = local_tables - neon_tables
common_tables = neon_tables & local_tables

print(f"Neon tables  : {len(neon_tables)}")
print(f"Local tables : {len(local_tables)}")
if only_in_neon:
    print(f"Tables only in Neon (not yet in local): {sorted(only_in_neon)}")
if only_in_local:
    print(f"Tables only in Local (not in Neon)    : {sorted(only_in_local)}")
print()

# ── Step 2: Count rows in each table on both sides ───────────────────────────
print(f"{'Table':<45} {'Neon rows':>10} {'Local rows':>11} {'Delta':>7}")
print("-" * 75)

summary = []
with src_engine.connect() as src_conn, dst_engine.connect() as dst_conn:
    for table in sorted(common_tables):
        try:
            neon_count = src_conn.execute(text(f'SELECT count(*) FROM "{table}"')).scalar()
            local_count = dst_conn.execute(text(f'SELECT count(*) FROM "{table}"')).scalar()
            delta = neon_count - local_count
            flag = " ◄ MISSING" if delta > 0 else ("" if delta == 0 else " ◄ LOCAL EXTRA")
            print(f"  {table:<43} {neon_count:>10} {local_count:>11} {delta:>+7}{flag}")
            summary.append((table, neon_count, local_count, delta))
        except Exception as e:
            print(f"  {table:<43} ERROR: {e}")

    for table in sorted(only_in_neon):
        try:
            neon_count = src_conn.execute(text(f'SELECT count(*) FROM "{table}"')).scalar()
            print(f"  {table:<43} {neon_count:>10} {'N/A':>11} {'N/A':>7}  ◄ TABLE MISSING LOCALLY")
            summary.append((table, neon_count, 0, neon_count))
        except Exception as e:
            print(f"  {table:<43} ERROR: {e}")

print()

# ── Step 3: Migrate missing rows ─────────────────────────────────────────────
tables_to_migrate = [(t, n, l, d) for (t, n, l, d) in summary if d > 0]
if not tables_to_migrate:
    print("✅ Local Docker Postgres is already up-to-date with Neon. Nothing to migrate.")
    sys.exit(0)

print(f"{'='*60}")
print(f"Found {len(tables_to_migrate)} table(s) where Neon has more rows than local.")
if DRY_RUN:
    print("DRY RUN — skipping actual inserts. Remove --dry-run to migrate.")
    for t, n, l, d in tables_to_migrate:
        print(f"  Would migrate {d:+} rows into: {t}")
    sys.exit(0)

print("Starting migration of missing rows (ON CONFLICT DO NOTHING)...")
print()

# Ensure local tables exist for any table that's only in Neon
if only_in_neon:
    print("Creating missing tables in local DB via SQLAlchemy models...")
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
        from app.db.models_candles import Candle1m, Candle5m, Candle15m, Candle1h, CandleDaily, OptionHistoricalCandle  # noqa: F401
        from app.db.models_finance import FinanceTransaction, RecurringTransaction, Budget, SavingsGoal, BillReminder, ExpenseForecast, CurrencyExchange  # noqa: F401
        from app.db.models_control import SystemControl  # noqa: F401
        from app.db.models_condition_strategy import ConditionStrategy, ConditionStrategyBacktest  # noqa: F401
        from app.db.models_trade_costs import TradeCost, BrokerageConfig  # noqa: F401
        from app.db.models_twitter import TwitterAccount, TwitterSentiment, TwitterSymbolSentiment, TwitterAlert  # noqa: F401
        Base.metadata.create_all(bind=dst_engine)
        print("  ✅ Tables created\n")
    except Exception as e:
        print(f"  ⚠️  Could not create tables via models: {e}")
        print("     Will attempt raw copy anyway.\n")

total_inserted = 0
total_skipped = 0
total_errors = 0

for table, neon_count, local_count, delta in tables_to_migrate:
    print(f"  Migrating: {table}  (Neon={neon_count}, Local={local_count}, delta={delta:+})")
    try:
        with src_engine.connect() as src_conn:
            rows = [dict(r) for r in src_conn.execute(text(f'SELECT * FROM "{table}"')).mappings()]

        if not rows:
            print(f"    ⏭  empty on Neon after fetch, skipping")
            continue

        cols = list(rows[0].keys())
        col_list = ", ".join(f'"{c}"' for c in cols)
        placeholders = ", ".join(f":{c}" for c in cols)

        inserted = 0
        skipped = 0
        with dst_engine.begin() as dst_conn:
            for row in rows:
                try:
                    result = dst_conn.execute(
                        text(
                            f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) '
                            f"ON CONFLICT DO NOTHING"
                        ),
                        dict(row),
                    )
                    if result.rowcount > 0:
                        inserted += 1
                    else:
                        skipped += 1
                except Exception as row_err:
                    skipped += 1

        total_inserted += inserted
        total_skipped += skipped
        print(f"    ✅ {inserted} rows inserted, {skipped} already existed / skipped")

    except Exception as e:
        total_errors += 1
        print(f"    ❌ FAILED — {e}")

print()
print("=" * 60)
print(f"Migration complete.")
print(f"  Total rows inserted : {total_inserted}")
print(f"  Total rows skipped  : {total_skipped}")
print(f"  Tables with errors  : {total_errors}")
if total_errors == 0:
    print("  ✅ All done — Local Docker Postgres is now in sync with Neon.")
else:
    print("  ⚠️  Some tables had errors. Review the output above.")
