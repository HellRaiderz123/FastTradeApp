"""Create and test an open position"""

import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import date

# Load .env
env_path = Path(__file__).parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path, override=True)

sys.path.insert(0, 'backend')

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent
from app.core.execution.zerodha import ZerodhaExecutionAdapter
from app.core.broker.zerodha.client import get_kite_client
from app.core.utils.time import now_ist
from app.core.market.expiry import get_current_weekly_expiry
import uuid

print("="*70)
print("CREATING AND TESTING OPEN POSITION")
print("="*70)
print()

db = SessionLocal()
try:
    # Create new position
    intent = ExecutionIntent()
    intent.run_id = "manual_test"
    intent.intent_id = "test_" + str(uuid.uuid4())[:8]
    intent.created_at = now_ist()
    intent.strategy = "BULL_PUT"
    intent.underlying = "NIFTY"
    
    weekly_expiry = get_current_weekly_expiry("NIFTY")
    intent.expiry = weekly_expiry
    
    intent.status = "EXECUTING"
    intent.executed = True
    intent.ticket = {
        "strategy": "BULL_PUT",
        "underlying": "NIFTY",
        "lot_size": 65,
        "lots": 1,
        "legs": [
            {
                "side": "SELL",
                "strike": 25800,
                "type": "PE",
            },
            {
                "side": "BUY",
                "strike": 25700,
                "type": "PE",
            }
        ]
    }
    
    # Execute to get prices
    kite = get_kite_client()
    zerodha = ZerodhaExecutionAdapter(kite_client=kite, dry_run=True)
    
    print(f"Executing position...")
    result = zerodha.execute(intent)
    
    intent.status = "EXECUTED"
    intent.execution_result = result
    intent.entry_credit = result.get("entry_credit", 0)
    intent.margin_required = result.get("margin_required", 0)
    
    # Add to DB
    db.add(intent)
    db.commit()
    
    print(f"[CREATED] {intent.intent_id}")
    print(f"  Entry Credit: {intent.entry_credit}")
    print()
    
    # Now test MTM
    print(f"Testing MTM calculation...")
    mtm = zerodha.mtm(intent)
    print(f"  MTM: {mtm:.2f}")
    
    print()
    print("Leg prices:")
    for i, leg in enumerate(intent.ticket.get("legs", []), 1):
        print(f"  Leg {i}: {leg.get('symbol')} @ {leg.get('price')}")

finally:
    db.close()

print("\n" + "="*70)
