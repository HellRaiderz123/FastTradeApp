"""
Fix string-encoded JSON columns remaining after SQLite→Postgres migration.
Covers: scanner_signal_history, strategy_runs, strategy_configs
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
import psycopg2
from urllib.parse import urlparse

DATABASE_URL = os.environ["DATABASE_URL"]
u = urlparse(DATABASE_URL)
conn = psycopg2.connect(host=u.hostname, port=u.port or 5432,
    dbname=u.path.lstrip("/").split("?")[0], user=u.username,
    password=u.password, sslmode="require")
conn.autocommit = False
cur = conn.cursor()

# These are JSON-type columns (not jsonb), so we use (col::text)::json cast
JSON_COLUMNS = [
    ("scanner_signal_history", "indicators_json"),
    ("scanner_signal_history", "signal_payload"),
    ("scanner_signal_history", "execution_payload"),
    ("strategy_runs", "signal"),
    ("strategy_runs", "context"),
    ("strategy_runs", "ticket"),
    ("strategy_configs", "parameters"),
]

print("Fixing string-encoded JSON columns...\n")
total_fixed = 0

for table, col in JSON_COLUMNS:
    try:
        # Find rows where the JSON value is a string (starts with a quote char)
        cur.execute(f"""
            SELECT id, {col}::text FROM {table}
            WHERE {col} IS NOT NULL AND {col}::text LIKE '"%%'
        """)
        rows = cur.fetchall()
        if not rows:
            print(f"  OK    {table}.{col} — no string-encoded rows")
            continue

        fixed = 0
        errors = 0
        for row_id, raw_val in rows:
            try:
                # raw_val is a Python string like '"{\\"key\\": \\"val\\"}"'
                # json.loads once to unwrap the outer string encoding
                inner = json.loads(raw_val)
                if isinstance(inner, str):
                    # Double-encoded: parse again
                    inner = json.loads(inner)
                cur.execute(
                    f"UPDATE {table} SET {col} = %s::json WHERE id = %s",
                    (json.dumps(inner), row_id)
                )
                fixed += 1
            except Exception as e:
                errors += 1
                print(f"    WARN  id={row_id}: {e}")

        conn.commit()
        total_fixed += fixed
        print(f"  FIXED {table}.{col} — {fixed} rows fixed, {errors} errors")
    except Exception as e:
        conn.rollback()
        print(f"  ERROR {table}.{col}: {e}")

cur.close()
conn.close()
print(f"\nDone. Total rows fixed: {total_fixed}")
