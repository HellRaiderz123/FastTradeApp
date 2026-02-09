"""Test MTM calculation with corrected symbol format"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path, override=True)

sys.path.insert(0, 'backend')

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent
from app.core.execution.zerodha import ZerodhaExecutionAdapter
from app.core.broker.zerodha.client import get_kite_client

print("=" * 70)
print("MTM CALCULATION WITH CORRECTED SYMBOLS")
print("=" * 70)
print()

try:
    # Get Zerodha adapter
    kite = get_kite_client()
    adapter = ZerodhaExecutionAdapter(kite_client=kite, dry_run=True)
    print("[OK] Zerodha Adapter initialized")
    print()
    
    # Get active positions
    db = SessionLocal()
    try:
        intents = (
            db.query(ExecutionIntent)
            .filter(ExecutionIntent.status == 'EXECUTED')
            .filter(ExecutionIntent.closed_at.is_(None))
            .all()
        )
        
        print(f"Found {len(intents)} active positions\n")
        
        for intent in intents[:1]:  # Test first one
            print(f"Testing: {intent.intent_id[:8]}...")
            print(f"  Strategy: {intent.strategy}")
            print(f"  Underlying: {intent.underlying}")
            print(f"  Entry Credit (DB): {intent.entry_credit}")
            print(f"  Ticket: {intent.ticket}")
            print()
            
            try:
                mtm = adapter.mtm(intent)
                print(f"  [OK] MTM Calculation: {mtm:.2f}")
            except Exception as e:
                print(f"  [ERROR] MTM Error: {type(e).__name__}: {e}")
    finally:
        db.close()

except Exception as e:
    print(f"[ERROR] Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
