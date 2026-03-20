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
cur = conn.cursor()

checks = [
    ("scanner_signal_history", "indicators_json"),
    ("scanner_signal_history", "signal_payload"),
    ("scanner_signal_history", "execution_payload"),
    ("strategy_runs", "signal"),
    ("strategy_runs", "context"),
    ("strategy_runs", "ticket"),
    ("strategy_configs", "parameters"),
]

for table, col in checks:
    cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NOT NULL")
    total = cur.fetchone()[0]
    cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {col}::text LIKE '\"%%'")
    strings = cur.fetchone()[0]
    print(f"{table}.{col}: total={total}, string-encoded={strings}")

cur.close()
conn.close()
