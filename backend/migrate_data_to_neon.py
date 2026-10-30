"""
Data migration: Local Docker PostgreSQL → Neon PostgreSQL

Usage:
    python migrate_data_to_neon.py           # dry-run: show row counts only
    python migrate_data_to_neon.py --migrate # actually migrate missing rows
    python migrate_data_to_neon.py --migrate --table strategy_runs  # single table
"""

import argparse
import os
import sys
from sqlalchemy import create_engine, inspect, text

SKIP_TABLES = {
    "candle_1m", "candle_5m", "candle_15m", "candle_1h", "candle_daily",
    "candles_1m", "candles_5m", "candles_15m", "candles_1h", "candles_daily",
    "option_historical_candles",
}

BATCH_SIZE = 500

LOCAL_URL = os.getenv("DATABASE_URL", "postgresql://fasttrade:your_new_password@localhost:5432/fasttrade")
NEON_URL  = os.getenv("NEON_SYNC_URL", "postgresql://neondb_owner:npg_FE5ZcbnaoA6q@ep-dry-cake-a11w18of-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require")


def fix_url(url):
    for p in ("postgresql://", "postgres://"):
        if url.startswith(p):
            return "postgresql+psycopg2://" + url[len(p):]
    return url


LOCAL_URL = fix_url(LOCAL_URL)
NEON_URL  = fix_url(NEON_URL)


def make_engines():
    local = create_engine(LOCAL_URL, pool_pre_ping=True)
    neon  = create_engine(NEON_URL, connect_args={"sslmode": "require"}, pool_pre_ping=True)
    return local, neon


def row_count(engine, table):
    with engine.connect() as c:
        return c.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar() or 0


def show_counts(local, neon, tables, neon_tables):
    print(f"\n{'TABLE':<42} {'LOCAL':>8} {'NEON':>8} {'DIFF':>8}")
    print("-" * 72)
    needs_sync = []
    for t in sorted(tables):
        lc = row_count(local, t)
        nc = row_count(neon, t) if t in neon_tables else 0
        diff = lc - nc
        flag = "  <- sync needed" if diff > 0 else ""
        print(f"{t:<42} {lc:>8} {nc:>8} {diff:>8}{flag}")
        if diff > 0:
            needs_sync.append(t)
    print("-" * 72)
    return needs_sync


def migrate_table(local, neon, table, insp_local):
    """Upsert all rows from local table into Neon in batches."""
    with local.connect() as src:
        result = src.execute(text(f'SELECT * FROM "{table}"'))
        rows = [dict(r) for r in result.mappings()]

    if not rows:
        print(f"  {table}: 0 rows - skip")
        return 0

    cols         = list(rows[0].keys())
    col_list     = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join(f":{c}" for c in cols)

    pk_info = insp_local.get_pk_constraint(table)
    pk_cols = pk_info.get("constrained_columns", []) if isinstance(pk_info, dict) else []

    if pk_cols:
        pk_clause  = ", ".join(f'"{c}"' for c in pk_cols)
        non_pk     = [c for c in cols if c not in pk_cols]
        upd_clause = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in non_pk) if non_pk else None
        conflict_sql = (
            f"ON CONFLICT ({pk_clause}) DO UPDATE SET {upd_clause}"
            if upd_clause
            else f"ON CONFLICT ({pk_clause}) DO NOTHING"
        )
    else:
        conflict_sql = "ON CONFLICT DO NOTHING"

    upsert_sql = f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) {conflict_sql}'

    ok = skip = 0
    total = len(rows)

    with neon.connect() as dst:
        for i in range(0, total, BATCH_SIZE):
            batch = rows[i: i + BATCH_SIZE]
            try:
                with dst.begin():
                    dst.execute(text(upsert_sql), batch)
                ok += len(batch)
            except Exception:
                # batch failed — row-by-row fallback
                for row in batch:
                    try:
                        with dst.begin():
                            dst.execute(text(upsert_sql), dict(row))
                        ok += 1
                    except Exception as e:
                        skip += 1
                        if skip <= 3:
                            print(f"    skip: {e}")
            if total > BATCH_SIZE:
                done = ok + skip
                pct  = min(100, int(done / total * 100))
                print(f"    {table}: {done}/{total} ({pct}%)...", end="\r", flush=True)

    if total > BATCH_SIZE:
        print()

    # Reset serial sequence so future inserts don't conflict
    if pk_cols and len(pk_cols) == 1:
        seq_col = pk_cols[0]
        try:
            with neon.connect() as dst:
                with dst.begin():
                    dst.execute(text(
                        f'SELECT setval(pg_get_serial_sequence(\'"{table}"\', \'{seq_col}\'), '
                        f'COALESCE((SELECT MAX("{seq_col}") FROM "{table}"), 1))'
                    ))
        except Exception:
            pass

    print(f"  OK {table}: {ok} upserted, {skip} skipped")
    return ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--migrate", action="store_true", help="Actually migrate data")
    parser.add_argument("--table", help="Migrate only this table")
    args = parser.parse_args()

    print(f"Local: {LOCAL_URL[:65]}...")
    print(f"Neon:  {NEON_URL[:65]}...")

    local, neon = make_engines()

    for label, eng in [("Local", local), ("Neon", neon)]:
        try:
            with eng.connect() as c:
                c.execute(text("SELECT 1"))
            print(f"Connected: {label}")
        except Exception as e:
            print(f"FAILED {label}: {e}")
            sys.exit(1)

    insp_local = inspect(local)
    insp_neon  = inspect(neon)

    all_local_tables = [t for t in insp_local.get_table_names() if t not in SKIP_TABLES]
    neon_tables      = set(insp_neon.get_table_names())
    tables           = [args.table] if args.table else all_local_tables

    print("\nRow counts (local vs Neon):")
    needs_sync = show_counts(local, neon, tables, neon_tables)

    if not needs_sync:
        print("\nAll tables already in sync.")
        return

    print(f"\n{len(needs_sync)} table(s) need migration.")

    if not args.migrate:
        print("Run with --migrate to copy data to Neon.")
        return

    print("\nStarting migration...\n")
    total = 0
    for t in needs_sync:
        if t not in neon_tables:
            print(f"  SKIP {t}: not on Neon (run compare_and_fix_dbs.py --fix first)")
            continue
        total += migrate_table(local, neon, t, insp_local)

    print(f"\nMigration complete: {total} total rows upserted.")
    print("\nFinal row counts:")
    show_counts(local, neon, tables, neon_tables)


if __name__ == "__main__":
    main()
