"""Check status of positions in database"""

import sys
sys.path.insert(0, 'backend')

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent

db = SessionLocal()
try:
    # Query all positions
    all_intents = db.query(ExecutionIntent).all()
    print(f"Total positions: {len(all_intents)}\n")
    
    for intent in all_intents:
        print(f"ID: {intent.intent_id[:8]}")
        print(f"  Status: {intent.status}")
        print(f"  Strategy: {intent.strategy}")
        print(f"  Closed at: {intent.closed_at}")
        print()
        
finally:
    db.close()
