import os
import sys
from sqlalchemy import create_engine, text, inspect

NEON_URL = os.getenv(
    "NEON_SYNC_URL",
    "postgresql+psycopg2://neondb_owner:npg_FE5ZcbnaoA6q"
    "@ep-dry-cake-a11w18of-pooler.ap-southeast-1.aws.neon.tech"
    "/neondb",
)
if not NEON_URL.startswith("postgresql+psycopg2"):
    NEON_URL = NEON_URL.replace("postgresql://", "postgresql+psycopg2://")

neon = create_engine(
    NEON_URL,
    connect_args={"sslmode": "require"},
    isolation_level="AUTOCOMMIT",
)

DDLS = {
    "ml_training_runs": """
        CREATE TABLE IF NOT EXISTS ml_training_runs (
            id SERIAL PRIMARY KEY,
            model_name VARCHAR NOT NULL,
            interval VARCHAR NOT NULL,
            symbols_count INTEGER,
            samples_count INTEGER,
            train_acc DOUBLE PRECISION,
            val_acc DOUBLE PRECISION,
            test_acc DOUBLE PRECISION,
            oob_score DOUBLE PRECISION,
            overfit_gap DOUBLE PRECISION,
            features JSONB,
            metadata_json JSONB,
            model_path VARCHAR,
            trained_at TIMESTAMPTZ
        )
    """,
    "ml_scan_results": """
        CREATE TABLE IF NOT EXISTS ml_scan_results (
            id SERIAL PRIMARY KEY,
            scan_type VARCHAR NOT NULL,
            symbol VARCHAR NOT NULL,
            buy_prob DOUBLE PRECISION,
            sell_prob DOUBLE PRECISION,
            margin DOUBLE PRECISION,
            momentum DOUBLE PRECISION,
            volume_strength DOUBLE PRECISION,
            quality_score DOUBLE PRECISION,
            price DOUBLE PRECISION,
            risk_flag VARCHAR,
            scanned_at TIMESTAMPTZ
        )
    """,
    "trade_journal": """
        CREATE TABLE IF NOT EXISTS trade_journal (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR,
            action VARCHAR,
            signal INTEGER,
            price DOUBLE PRECISION,
            quantity INTEGER,
            pnl DOUBLE PRECISION,
            reason VARCHAR,
            interval VARCHAR,
            entry_json JSONB,
            recorded_at TIMESTAMPTZ
        )
    """,
}

print("Connecting to Neon...")
with neon.connect() as conn:
    for name, ddl in DDLS.items():
        try:
            conn.execute(text(ddl))
            print(f"  OK: {name}")
        except Exception as e:
            print(f"  ERROR {name}: {e}")

print("\nVerifying...")
insp = inspect(neon)
tables = set(insp.get_table_names())
print(f"Total tables on Neon: {len(tables)}")
for name in DDLS:
    status = "FOUND" if name in tables else "MISSING"
    cols = len(insp.get_columns(name)) if name in tables else 0
    print(f"  {status}: {name}  ({cols} cols)")
