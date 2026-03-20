"""
Fix string-encoded JSON columns remaining after SQLite→Postgres migration.
Uses a single SQL UPDATE per column for speed (no row-by-row Python loop).
Covers: scanner_signal_history, strategy_runs, strategy_configs
"""
import os, sys
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

# These are JSON-type columns (not jsonb).
# Strategy: cast to text, strip outer quotes, then cast back to json.
# The stored value looks like: '"{\\"key\\": \\"val\\"}"'
# After ::text it becomes: "\"{ ... }\""  (a JSON string containing JSON)
# We use: (trim(both '"' from col::text))::json  — but that won't handle escape sequences.
# Better: use json_strip_nulls trick or just do it in Python for correctness.
# Actually the cleanest SQL approach: col::text::json gives us the string value,
# then we need to parse that string as JSON again.
# In Postgres: (col #>> '{}')::json  — extracts the text value of a JSON string, then re-parses.

JSON_COLUMNS = [
    ("scanner_signal_history", "indicators_json"),
    ("scanner_signal_history", "signal_payload"),
    ("strategy_runs", "signal"),
    ("strategy_runs", "context"),
    ("strategy_runs", "ticket"),
    ("strategy_configs", "parameters"),
]

print("Fixing string-encoded JSON columns (fast SQL method)...\n")
total_fixed = 0

for table, col in JSON_COLUMNS:
    try:
        # Check how many need fixing
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NOT NULL AND {col}::text LIKE '\"%%'")
        count = cur.fetchone()[0]
        if count == 0:
            print(f"  OK    {table}.{col} — no string-encoded rows")
            continue

        # Use Postgres JSON path operator to extract the string value, then re-cast to json
        # col #>> '{}' extracts the top-level value as text (unwraps the outer JSON string)
        cur.execute(f"""
            UPDATE {table}
            SET {col} = ({col} #>> '{{}}')::json
            WHERE {col} IS NOT NULL AND {col}::text LIKE '"%%'
        """)
        n = cur.rowcount
        conn.commit()
        total_fixed += n
        print(f"  FIXED {table}.{col} — {n} rows fixed")
    except Exception as e:
        conn.rollback()
        print(f"  ERROR {table}.{col}: {e}")

cur.close()
conn.close()
print(f"\nDone. Total rows fixed: {total_fixed}")
