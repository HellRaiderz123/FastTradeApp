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

JSON_COLUMNS = [
    ("strategy_runs", "signal"), ("strategy_runs", "context"), ("strategy_runs", "ticket"),
    ("strategy_configs", "parameters"),
    ("backtest_results", "trades"), ("backtest_results", "equity_curve"), ("backtest_results", "drawdown_periods"),
    ("alert_rules", "condition"), ("alert_rules", "notify_via"), ("alert_rules", "action_params"),
]

def table_exists(t):
    cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = %s)", (t,))
    return cur.fetchone()[0]

print("Fixing double-encoded JSON columns...\n")
for table, col in JSON_COLUMNS:
    try:
        if not table_exists(table):
            print(f"  SKIP  {table}.{col} (not found)"); continue
        cur.execute(f"UPDATE {table} SET {col} = ({col}::text)::jsonb WHERE {col} IS NOT NULL AND ({col}::text) ~ '^[{{[]]'")
        n = cur.rowcount; conn.commit()
        print(f"  OK    {table}.{col} -> {n} rows updated")
    except Exception as e:
        conn.rollback(); print(f"  ERROR {table}.{col}: {e}")

cur.close(); conn.close()
print("\nDone.")
