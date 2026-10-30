"""
Compare local Docker PostgreSQL vs Neon PostgreSQL:
  - Missing tables
  - Missing columns (with type)
  - Extra tables/columns on Neon not in local

Then apply fixes: create missing tables + add missing columns on Neon.

Usage:
    cd backend
    python compare_and_fix_dbs.py [--fix]
"""

import argparse
import os
import sys
from sqlalchemy import create_engine, inspect, text

def _fix_url(url: str) -> str:
    """Ensure URL uses psycopg2 driver explicitly."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


LOCAL_URL = _fix_url(os.getenv(
    "DATABASE_URL",
    "postgresql://fasttrade:your_new_password@localhost:5432/fasttrade",
))
NEON_URL = _fix_url(os.getenv(
    "NEON_SYNC_URL",
    "postgresql://neondb_owner:npg_FE5ZcbnaoA6q"
    "@ep-dry-cake-a11w18of-pooler.ap-southeast-1.aws.neon.tech"
    "/neondb?sslmode=require",
))

SKIP_TABLES = {
    "candle_1m", "candle_5m", "candle_15m", "candle_1h", "candle_daily",
    "candles_1m", "candles_5m", "candles_15m", "candles_1h", "candles_daily",
    "option_historical_candles",
}


def make_engine(url, is_neon=False):
    kwargs = {"pool_pre_ping": True}
    if is_neon:
        kwargs["connect_args"] = {"sslmode": "require"}
    return create_engine(url, **kwargs)


def get_schema(engine):
    """Return {table: {col: type_str}} for all non-skipped tables."""
    insp = inspect(engine)
    schema = {}
    for table in insp.get_table_names():
        if table in SKIP_TABLES:
            continue
        cols = {}
        for col in insp.get_columns(table):
            cols[col["name"]] = str(col["type"])
        schema[table] = cols
    return schema


def pg_type_for(type_str: str) -> str:
    """Map SQLAlchemy type string → Postgres DDL type."""
    t = type_str.upper()
    if "VARCHAR" in t or "STRING" in t or "TEXT" in t:
        return "TEXT"
    if "INTEGER" in t or "INT" in t:
        return "INTEGER"
    if "FLOAT" in t or "NUMERIC" in t or "REAL" in t or "DOUBLE" in t:
        return "DOUBLE PRECISION"
    if "BOOLEAN" in t or "BOOL" in t:
        return "BOOLEAN"
    if "DATETIME" in t or "TIMESTAMP" in t:
        return "TIMESTAMPTZ"
    if "DATE" in t:
        return "DATE"
    if "JSON" in t:
        return "JSONB"
    return "TEXT"  # safe fallback


def compare(local_schema, neon_schema):
    local_tables = set(local_schema)
    neon_tables = set(neon_schema)

    missing_tables = local_tables - neon_tables
    extra_tables = neon_tables - local_tables
    common_tables = local_tables & neon_tables

    missing_cols = {}   # {table: {col: type}}
    extra_cols = {}     # {table: [col]}

    for table in sorted(common_tables):
        local_cols = local_schema[table]
        neon_cols = neon_schema[table]
        miss = {c: t for c, t in local_cols.items() if c not in neon_cols}
        extra = [c for c in neon_cols if c not in local_cols]
        if miss:
            missing_cols[table] = miss
        if extra:
            extra_cols[table] = extra

    return missing_tables, extra_tables, missing_cols, extra_cols


def print_report(missing_tables, extra_tables, missing_cols, extra_cols):
    print("\n" + "=" * 60)
    print("DATABASE SCHEMA COMPARISON REPORT")
    print("=" * 60)

    if missing_tables:
        print(f"\n❌ Tables in LOCAL but MISSING on Neon ({len(missing_tables)}):")
        for t in sorted(missing_tables):
            print(f"   - {t}")
    else:
        print("\n✅ No missing tables on Neon")

    if extra_tables:
        print(f"\n⚠️  Tables on Neon but NOT in local ({len(extra_tables)}):")
        for t in sorted(extra_tables):
            print(f"   - {t}")

    if missing_cols:
        print(f"\n❌ Missing columns on Neon ({sum(len(v) for v in missing_cols.values())} total):")
        for table, cols in sorted(missing_cols.items()):
            print(f"   {table}:")
            for col, typ in cols.items():
                print(f"      + {col}  [{typ}]")
    else:
        print("\n✅ No missing columns on Neon")

    if extra_cols:
        print(f"\n⚠️  Extra columns on Neon not in local:")
        for table, cols in sorted(extra_cols.items()):
            print(f"   {table}: {', '.join(cols)}")

    print()


def fix_neon(neon_engine, local_engine, missing_tables, missing_cols, local_schema):
    """Apply fixes to Neon: create missing tables + add missing columns."""
    # 1. Create missing tables using SQLAlchemy models
    if missing_tables:
        print("🔧 Creating missing tables on Neon via SQLAlchemy metadata...")
        try:
            # Import all models so Base.metadata is fully populated
            from app.db.session import Base
            import app.db.models  # noqa
            import app.db.models_intent  # noqa
            import app.db.models_control  # noqa
            import app.db.models_candles  # noqa
            import app.db.models_signal_outcome  # noqa
            import app.db.models_zerodha  # noqa
            import app.db.models_indmoney  # noqa
            import app.db.models_instruments  # noqa
            import app.db.models_ai_log  # noqa
            import app.db.models_fii_dii  # noqa
            import app.db.models_watchlist  # noqa
            import app.db.models_trade_costs  # noqa
            import app.db.models_nse  # noqa
            import app.db.models_twitter  # noqa
            import app.db.models_fundamentals  # noqa
            import app.db.models_finance  # noqa
            import app.db.models_condition_strategy  # noqa
            import app.db.models_scanner_signal  # noqa
            import app.db.models_stock_holding  # noqa
            import app.db.models_risk  # noqa
            import app.db.models_notification  # noqa
            import app.db.models_alexa  # noqa
            import app.db.models_ai_decisions  # noqa
            import app.db.models_auto_trader  # noqa
            from app.core.scalp.scalp_paper_trader import ScalpTrade  # noqa

            # Only create the missing tables
            tables_to_create = [
                t for name, t in Base.metadata.tables.items()
                if name in missing_tables
            ]
            Base.metadata.create_all(bind=neon_engine, tables=tables_to_create)
            for t in sorted(missing_tables):
                print(f"   ✅ Created table: {t}")
        except Exception as e:
            print(f"   ❌ Failed to create tables via metadata: {e}")
            print("      Falling back to raw SQL inspection...")
            _create_tables_raw(neon_engine, local_engine, missing_tables)

    # 2. Add missing columns
    if missing_cols:
        print("\n🔧 Adding missing columns on Neon...")
        with neon_engine.connect() as conn:
            for table, cols in sorted(missing_cols.items()):
                for col, type_str in cols.items():
                    pg_type = pg_type_for(type_str)
                    sql = f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{col}" {pg_type};'
                    try:
                        conn.execute(text(sql))
                        conn.commit()
                        print(f"   ✅ {table}.{col}  [{pg_type}]")
                    except Exception as e:
                        print(f"   ❌ {table}.{col}: {e}")


def _create_tables_raw(neon_engine, local_engine, missing_tables):
    """Fallback: copy CREATE TABLE DDL from local to Neon using pg_dump style."""
    local_insp = inspect(local_engine)
    for table in sorted(missing_tables):
        try:
            cols = local_insp.get_columns(table)
            pk = local_insp.get_pk_constraint(table).get("constrained_columns", [])
            col_defs = []
            for c in cols:
                pg_type = pg_type_for(str(c["type"]))
                nullable = "" if c.get("nullable", True) else " NOT NULL"
                default = ""
                if c.get("default") is not None:
                    default = f" DEFAULT {c['default']}"
                col_defs.append(f'  "{c["name"]}" {pg_type}{nullable}{default}')
            if pk:
                pk_str = ", ".join(f'"{c}"' for c in pk)
                col_defs.append(f"  PRIMARY KEY ({pk_str})")
            ddl = f'CREATE TABLE IF NOT EXISTS "{table}" (\n' + ",\n".join(col_defs) + "\n);"
            with neon_engine.connect() as conn:
                conn.execute(text(ddl))
                conn.commit()
            print(f"   ✅ Created (raw): {table}")
        except Exception as e:
            print(f"   ❌ Could not create {table}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Compare and optionally fix local vs Neon PostgreSQL schemas")
    parser.add_argument("--fix", action="store_true", help="Apply fixes to Neon (create tables, add columns)")
    args = parser.parse_args()

    print(f"🔌 Local:  {LOCAL_URL[:60]}...")
    print(f"🔌 Neon:   {NEON_URL[:60]}...")

    try:
        local_engine = make_engine(LOCAL_URL, is_neon=False)
        with local_engine.connect() as c:
            c.execute(text("SELECT 1"))
        print("✅ Local DB connected")
    except Exception as e:
        print(f"❌ Cannot connect to local DB: {e}")
        sys.exit(1)

    try:
        neon_engine = make_engine(NEON_URL, is_neon=True)
        with neon_engine.connect() as c:
            c.execute(text("SELECT 1"))
        print("✅ Neon DB connected")
    except Exception as e:
        print(f"❌ Cannot connect to Neon DB: {e}")
        sys.exit(1)

    print("\n📊 Fetching schemas...")
    local_schema = get_schema(local_engine)
    neon_schema = get_schema(neon_engine)
    print(f"   Local tables: {len(local_schema)}")
    print(f"   Neon  tables: {len(neon_schema)}")

    missing_tables, extra_tables, missing_cols, extra_cols = compare(local_schema, neon_schema)
    print_report(missing_tables, extra_tables, missing_cols, extra_cols)

    has_issues = bool(missing_tables or missing_cols)

    if not has_issues:
        print("🎉 Both databases are in sync — no fixes needed.")
        return

    if args.fix:
        fix_neon(neon_engine, local_engine, missing_tables, missing_cols, local_schema)
        print("\n✅ Fix complete. Re-running comparison to verify...\n")
        neon_schema2 = get_schema(neon_engine)
        mt2, et2, mc2, ec2 = compare(local_schema, neon_schema2)
        print_report(mt2, et2, mc2, ec2)
        if not mt2 and not mc2:
            print("🎉 Neon is now fully in sync with local!")
        else:
            print("⚠️  Some issues remain — check errors above.")
    else:
        print("ℹ️  Run with --fix to apply these changes to Neon.")


if __name__ == "__main__":
    main()
