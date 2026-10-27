from app.db.session import engine
from sqlalchemy import text

# Add new columns if they don't exist
new_cols = [
    ("opm_pct", "FLOAT"),
    ("npm_pct", "FLOAT"),
    ("eps", "FLOAT"),
    ("debt_to_equity", "FLOAT"),
    ("key_points", "TEXT"),
    ("shareholding_quarterly", "JSON"),
    ("annual_reports", "JSON"),
    ("credit_ratings", "JSON"),
    ("quarterly_results", "JSON"),
    ("pnl_annual", "JSON"),
]

with engine.connect() as conn:
    for col, typ in new_cols:
        try:
            conn.execute(text(f"ALTER TABLE fundamentals_cache ADD COLUMN {col} {typ}"))
            conn.commit()
            print(f"Added column: {col}")
        except Exception as e:
            print(f"Skip {col}: {e}")

# Force-refresh all cached symbols
from app.db.session import SessionLocal
from app.db.models_fundamentals import FundamentalsCache
from datetime import datetime, timedelta

db = SessionLocal()
rows = db.query(FundamentalsCache).all()
print(f"Invalidating {len(rows)} cached rows to force re-fetch...")
for row in rows:
    row.cached_at = datetime.utcnow() - timedelta(days=100)
db.commit()
db.close()
print("Done — next API call will re-fetch fresh data.")
