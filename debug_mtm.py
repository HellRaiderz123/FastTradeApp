import sys, traceback
sys.path.insert(0, '/app')

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent
from app.core.execution.paper import PaperExecutionAdapter
from app.core.execution.base import get_ticket
from app.core.market.ltp import get_ltp

db = SessionLocal()
adapter = PaperExecutionAdapter()
intents = db.query(ExecutionIntent).filter(ExecutionIntent.status == 'EXECUTED').all()
print(f"Found {len(intents)} EXECUTED intents", flush=True)

for i in intents:
    try:
        ticket = get_ticket(i)
        legs = ticket.get('legs', [])
        symbols = [leg.get('symbol') or '' for leg in legs]
        ltp_map = get_ltp(symbols)
        mtm = adapter.mtm(i)
        print(f"{i.underlying}: symbols={symbols} ltp={ltp_map} mtm={mtm} db_pnl={i.pnl}", flush=True)
    except Exception as e:
        traceback.print_exc()
        print(f"{i.underlying}: ERROR {e}", flush=True)

db.close()
