"""Check what's actually stored in the position"""

import sys
sys.path.insert(0, 'backend')

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent
import json

db = SessionLocal()
try:
    intents = (
        db.query(ExecutionIntent)
        .filter(ExecutionIntent.status == 'EXECUTED')
        .filter(ExecutionIntent.closed_at.is_(None))
        .all()
    )
    
    for intent in intents:
        print(f"\n{'='*70}")
        print(f"Intent: {intent.intent_id[:8]}")
        print(f"Entry Credit (field): {intent.entry_credit}")
        print(f"Execution Result: {intent.execution_result}")
        print(f"\nTicket Details:")
        if intent.ticket:
            print(json.dumps(intent.ticket, indent=2))
        print(f"{'='*70}\n")
finally:
    db.close()
