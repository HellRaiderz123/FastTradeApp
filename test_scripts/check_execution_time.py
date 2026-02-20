"""Check when the position was executed - using execution_result timestamp"""

import sys
sys.path.insert(0, 'backend')

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent
from datetime import datetime
import json

db = SessionLocal()
try:
    intents = (
        db.query(ExecutionIntent)
        .filter(ExecutionIntent.status == 'EXECUTED')
        .filter(ExecutionIntent.closed_at.is_(None))
        .all()
    )
    
    print("="*70)
    print("POSITION EXECUTION TIMESTAMPS")
    print("="*70)
    
    for intent in intents:
        print(f"\nIntent: {intent.intent_id[:8]}")

        if intent.execution_result:
            created_at = intent.execution_result.get("created_at")
            print(f"Execution created_at: {created_at}")
            entry_credit = intent.execution_result.get("entry_credit")
            print(f"Entry Credit from execution: {entry_credit}")
            
            if created_at:
                # Parse time - format is '2026-02-09T09:55:31.125079+05:30'
                try:
                    dt = datetime.fromisoformat(created_at)
                    print(f"Parsed datetime: {dt}")
                    print(f"Hour: {dt.hour}, Minute: {dt.minute}")
                    
                    # Check if market is open (9:15 AM - 3:30 PM IST)
                    time_in_minutes = dt.hour * 60 + dt.minute
                    market_open = 9 * 60 + 15  # 9:15 AM
                    market_close = 15 * 60 + 30  # 3:30 PM
                    if market_open <= time_in_minutes <= market_close:
                        print("✅ During market hours (9:15 AM - 3:30 PM IST)")
                    else:
                        print(f"❌ OUTSIDE market hours - {dt.strftime('%H:%M %Z')}")
                except Exception as e:
                    print(f"Error parsing time: {e}")

finally:
    db.close()
