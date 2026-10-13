import sys
sys.path.insert(0, '/app')
from app.db.session import SessionLocal
from app.db.models_condition_strategy import ConditionStrategy
db = SessionLocal()
strats = db.query(ConditionStrategy).all()
for s in strats:
    ec = s.entry_conditions or []
    xc = (s.exit_config or {}).get('exit_conditions') or []
    print('id=%d n=%s' % (s.id, s.name[:40]))
    for i, c in enumerate(ec):
        print('  E%d ind=%s val=%r params=%r' % (i, c.get('indicator'), c.get('value'), c.get('params')))
    for i, c in enumerate(xc):
        print('  X%d ind=%s val=%r params=%r' % (i, c.get('indicator'), c.get('value'), c.get('params')))
db.close()
