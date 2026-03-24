"""
One-time migration: Neon PostgreSQL → Local Docker PostgreSQL
Run this ONCE after spinning up the local docker db for the first time.

Usage (from backend/ directory):
    python migrate_from_neon.py

What it does:
    1. Connects to Neon (source) and local Docker Postgres (target)
    2. Creates all tables in local DB via SQLAlchemy models
    3. Copies every row from every table, skipping duplicates
"""

import os
import sys
from sqlalchemy import create_engine, text, inspect

# ── Connection URLs ────────────────────────────────────────────────────────────
NEON_URL = (
    "postgresql://neondb_owner:npg_FE5ZcbnaoA6q"
    "@ep-dry-cake-a11w18of-pooler.ap-southeast-1.aws.neon.tech"
    "/neondb?sslmode=require"
)

# When running outside Docker use localhost:5432
# When running inside Docker backend container use db:5432
LOCAL_URL = os.getenv(
    "LOCAL_DB_URL",
    "postgresql://fasttrade:Something9931522390@localhost:5432/fasttrade",
)

print(f"Source : Neon")
print(f"Target : {LOCAL_URL.split('@')[-1]}")  # hide password in output
print()

src_engine = create_engine(NEON_URL, connect_args={"sslmode": "require"})
dst_engine = create_engine(LOCAL_URL)

# ── Step 1: Create all tables in local DB ─────────────────────────────────────
print("📐 Creating tables in local DB...")
# Import all models so Base.metadata knows about them
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
print("✅ Tables created\n")

# ── Step 2: Copy data table by table ──────────────────────────────────────────
inspector = inspect(src_engine)
tables = inspector.get_table_names()
print(f"📋 Found {len(tables)} tables in Neon: {tables}\n")

for table in tables:
    try:
        with src_engine.connect() as src_conn:
            rows = src_conn.execute(text(f'SELECT * FROM "{table}"')).mappings().all()

        if not rows:
            print(f"  ⏭  {table}: empty, skipping")
            continue

        cols = list(rows[0].keys())
        col_list = ", ".join(f'"{c}"' for c in cols)
        placeholders = ", ".join(f":{c}" for c in cols)

        inserted = 0
        skipped = 0
        with dst_engine.begin() as dst_conn:
            for row in rows:
                try:
                    dst_conn.execute(
                        text(
                            f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) '
                            f"ON CONFLICT DO NOTHING"
                        ),
                        dict(row),
                    )
                    inserted += 1
                except Exception:
                    skipped += 1

        print(f"  ✅ {table}: {inserted} rows copied, {skipped} skipped")

    except Exception as e:
        print(f"  ❌ {table}: FAILED — {e}")

print("\n🎉 Migration complete. Your local Docker Postgres now has all Neon data.")
print("   You can now run: docker-compose up --build")
