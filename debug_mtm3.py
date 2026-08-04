import sys
sys.path.insert(0, '/app')
from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent
from app.core.execution.paper import PaperExecutionAdapter

db = SessionLocal()
adapter = PaperExecutionAdapter()
intents = db.query(ExecutionIntent).filter(ExecutionIntent.status == 'EXECUTED').all()
print(f"Found {len(intents)} intents", flush=True)
for i in intents:
    try:
        mtm = adapter.mtm(i)
        print(f"{i.underlying}: mtm={mtm}", flush=True)
    except Exception as e:
        print(f"{i.underlying}: ERROR {e}", flush=True)
db.close()
