"""
migrate_to_postgres.py
-----------------------
Migrates all data from local SQLite (trading.db) to Neon PostgreSQL.

Usage:
    cd backend
    python migrate_to_postgres.py

Requirements:
    - DATABASE_URL must be set in .env pointing to Neon Postgres
    - trading.db must exist in backend/
    - psycopg2-binary must be installed (already in requirements.txt)
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# ── Load .env FIRST ──────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("migrate")

# ── Validate env ─────────────────────────────────────────────────────────────
POSTGRES_URL = os.getenv("DATABASE_URL", "")
SQLITE_PATH  = Path(__file__).parent / "trading.db"

if not POSTGRES_URL.startswith("postgresql"):
    log.error("DATABASE_URL is not a PostgreSQL URL. Set it in backend/.env first.")
    sys.exit(1)

if not SQLITE_PATH.exists():
    log.error(f"SQLite file not found: {SQLITE_PATH}")
    sys.exit(1)

log.info(f"Source : {SQLITE_PATH}  ({SQLITE_PATH.stat().st_size / 1024 / 1024:.1f} MB)")
log.info(f"Target : {POSTGRES_URL.split('@')[1] if '@' in POSTGRES_URL else POSTGRES_URL}")

# ── Create engines ────────────────────────────────────────────────────────────
from sqlalchemy import create_engine, text, inspect, MetaData, Table
from sqlalchemy.orm import sessionmaker

sqlite_engine = create_engine(
    f"sqlite:///{SQLITE_PATH.as_posix()}",
    connect_args={"check_same_thread": False},
)

pg_engine = create_engine(
    POSTGRES_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={
        "sslmode": "require",
        "options": "-c timezone=Asia/Kolkata",
    },
)

# ── Create all tables in Postgres from SQLAlchemy models ─────────────────────
log.info("Creating tables in PostgreSQL...")

# Import all models so Base.metadata is fully populated
from app.db.session import Base  # noqa: must come after engine setup

# Override engine to point at Postgres for table creation
from app.db import models               # noqa
from app.db import models_candles       # noqa
from app.db import models_intent        # noqa
from app.db import models_finance       # noqa
from app.db import models_auto_trader   # noqa
from app.db import models_risk          # noqa
from app.db import models_notification  # noqa
from app.db import models_zerodha       # noqa
from app.db import models_watchlist     # noqa
from app.db import models_twitter       # noqa
from app.db import models_scanner_signal  # noqa
from app.db import models_signal_outcome  # noqa
from app.db import models_trade_costs   # noqa
from app.db import models_control       # noqa

# Temporarily bind Base to pg_engine for table creation
Base.metadata.create_all(bind=pg_engine)
log.info("✅ All tables created in PostgreSQL")

# ── Migrate table by table ────────────────────────────────────────────────────
sqlite_inspector = inspect(sqlite_engine)
pg_inspector     = inspect(pg_engine)

sqlite_tables = set(sqlite_inspector.get_table_names())
pg_tables     = set(pg_inspector.get_table_names())

# Tables to migrate (intersection of what exists in SQLite and Postgres)
tables_to_migrate = sorted(sqlite_tables & pg_tables)

# Skip internal SQLite tables
SKIP_TABLES = {"sqlite_sequence", "sqlite_master"}
tables_to_migrate = [t for t in tables_to_migrate if t not in SKIP_TABLES]

log.info(f"Tables to migrate: {len(tables_to_migrate)}")

sqlite_meta = MetaData()
sqlite_meta.reflect(bind=sqlite_engine)

pg_meta = MetaData()
pg_meta.reflect(bind=pg_engine)

total_rows = 0
errors = []

with pg_engine.begin() as pg_conn:
    for table_name in tables_to_migrate:
        try:
            # Read all rows from SQLite
            with sqlite_engine.connect() as sqlite_conn:
                result = sqlite_conn.execute(text(f'SELECT * FROM "{table_name}"'))
                rows = result.fetchall()
                columns = list(result.keys())

            if not rows:
                log.info(f"  {table_name:<45} 0 rows  (skipped)")
                continue

            # Convert rows to list of dicts
            data = [dict(zip(columns, row)) for row in rows]

            # Truncate target table first to avoid duplicates on re-run
            pg_conn.execute(text(f'TRUNCATE TABLE "{table_name}" RESTART IDENTITY CASCADE'))

            # Insert in batches of 1000 for speed
            pg_table = pg_meta.tables[table_name]
            batch_size = 1000
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                pg_conn.execute(pg_table.insert(), batch)
                # Show progress for large tables
                if len(data) > batch_size:
                    done = min(i + batch_size, len(data))
                    log.info(f"    → {done}/{len(data)} rows...")

            total_rows += len(data)
            log.info(f"  ✅ {table_name:<45} {len(data):>6} rows")

        except Exception as e:
            errors.append((table_name, str(e)))
            log.warning(f"  ⚠️  {table_name:<45} FAILED: {e}")

# ── Summary ───────────────────────────────────────────────────────────────────
log.info("")
log.info("=" * 60)
log.info(f"Migration complete: {total_rows} total rows migrated")
if errors:
    log.warning(f"{len(errors)} table(s) had errors:")
    for tbl, err in errors:
        log.warning(f"  - {tbl}: {err}")
else:
    log.info("No errors.")
log.info("=" * 60)
