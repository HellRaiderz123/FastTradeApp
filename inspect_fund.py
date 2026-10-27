from app.db.session import SessionLocal
from app.db.models_fundamentals import FundamentalsCache
import json
db = SessionLocal()
rows = db.query(FundamentalsCache).all()
print('total rows:', len(rows))
if rows:
    row = rows[0]
    print('symbol:', row.symbol)
    rr = row.raw_ref or {}
    print('raw_ref keys:', list(rr.keys()))
    print(json.dumps(rr, indent=2)[:4000])
    if row.peer_comparison:
        print('\npeer_comparison[0] keys:', list(row.peer_comparison[0].keys()))
db.close()
