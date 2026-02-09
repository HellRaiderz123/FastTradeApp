"""Check if old position has leg prices stored"""

import sys
import json
sys.path.insert(0, 'backend')

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent

db = SessionLocal()
try:
    intents = (
        db.query(ExecutionIntent)
        .filter(ExecutionIntent.status == 'EXECUTED')
        .filter(ExecutionIntent.closed_at.is_(None))
        .all()
    )
    
    print("="*70)
    print("CHECKING IF OLD POSITION HAS LEG PRICES")
    print("="*70)
    
    for intent in intents[:1]:
        print(f"\nIntent: {intent.intent_id[:8]}")
        ticket = intent.ticket or {}
        
        print(f"\nLegs in ticket:")
        for i, leg in enumerate(ticket.get("legs", []), 1):
            print(f"  Leg {i}:")
            for k, v in leg.items():
                print(f"    {k}: {v}")
        
        # Check if all legs have prices
        has_all_prices = all(leg.get("price") is not None for leg in ticket.get("legs", []))
        print(f"\nAll legs have prices: {has_all_prices}")
        
finally:
    db.close()

print("\n" + "="*70)
