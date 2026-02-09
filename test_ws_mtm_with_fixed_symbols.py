"""Test WebSocket position updates with fixed symbols"""

import sys
import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path, override=True)

sys.path.insert(0, 'backend')

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent
from app.core.execution.paper import PaperExecutionAdapter
from app.core.execution.zerodha import ZerodhaExecutionAdapter
from app.core.broker.zerodha.client import get_kite_client
from app.core.utils.time import now_ist

print("="*70)
print("TESTING MTM CALCULATION WITH FIXED SYMBOLS")
print("="*70)
print()

db = SessionLocal()
try:
    # Find one open position
    intent = (
        db.query(ExecutionIntent)
        .filter(ExecutionIntent.status == 'EXECUTED')
        .filter(ExecutionIntent.closed_at.is_(None))
        .first()
    )
    
    if not intent:
        print("[NO OPEN POSITIONS FOUND]")
    else:
        print(f"Testing: {intent.intent_id[:8]}")
        print(f"  Strategy: {intent.strategy}")
        print(f"  Mode: {intent.execution_result.get('mode') if intent.execution_result else 'UNKNOWN'}")
        print()
        
        #  Test paper adapter
        paper = PaperExecutionAdapter()
        try:
            mtm_paper = paper.mtm(intent)
            print(f"  Paper MTM: {mtm_paper:.2f}")
        except Exception as e:
            print(f"  Paper MTM: ERROR - {e}")
        
        # Test zerodha adapter
        try:
            kite = get_kite_client()
            zerodha = ZerodhaExecutionAdapter(kite_client=kite, dry_run=True)
            mtm_zerodha = zerodha.mtm(intent)
            print(f"  Zerodha MTM: {mtm_zerodha:.2f}")
        except Exception as e:
            print(f"  Zerodha MTM: ERROR - {type(e).__name__}: {str(e)[:50]}")
        
        print()
        print("Leg prices in ticket:")
        for i, leg in enumerate(intent.ticket.get("legs", []), 1):
            print(f"  Leg {i}: {leg.get('symbol')} @ {leg.get('price')}")

finally:
    db.close()

print("\n" + "="*70)
