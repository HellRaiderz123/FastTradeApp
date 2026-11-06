import time
import app.core.market.scheduler as sched

# Full reset
sched._LAST_FILING_POLL_AT = time.time() - 3600
sched._IS_FIRST_FILING_RUN = True
sched._NOTIFIED_FILINGS.clear()

print("Running scan...", flush=True)
sched._check_nse_high_impact_filings()

# Wait for background PDF threads
print("Waiting for PDF threads...", flush=True)
time.sleep(20)

from app.db.session import SessionLocal
from app.db.models_filing_analysis import NseFilingAnalysis
db = SessionLocal()
rows = db.query(NseFilingAnalysis).all()
print(f"Total rows: {len(rows)}", flush=True)
for r in rows:
    print(f"  {r.symbol} | passed={r.passed_filter} | {r.filter_reason} | {r.sentiment} | pdf={r.pdf_extracted}", flush=True)
db.close()
