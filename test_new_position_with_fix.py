"""Create a new test position and check if entry_credit is calculated correctly"""

import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import date, datetime, timedelta
import json

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

print("="*70)
print("CREATING NEW TEST POSITION WITH CORRECTED SYMBOLS")
print("="*70)
print()

try:
    db = SessionLocal()
    
    # Get weekly expiry for NIFTY
    weekly_expiry = get_current_weekly_expiry("NIFTY")
    print(f"Weekly NIFTY expiry: {weekly_expiry}")
    
    # Create a new execution intent for BULL_PUT
    intent = ExecutionIntent()
    intent.intent_id = "test_" + now_ist().isoformat().replace(":", "-")
    intent.created_at = now_ist()
    intent.strategy = "BULL_PUT"
    intent.underlying = "NIFTY"
    intent.expiry = weekly_expiry
    intent.status = "EXECUTING"
    intent.executed = False
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
    
    # Now execute to get entry_credit
    kite = get_kite_client()
    executor = ZerodhaExecutionAdapter(kite_client=kite, dry_run=True)
    
    print(f"Executing BULL_PUT with expiry {weekly_expiry}...")
    result = executor.execute(intent)
    
    print(f"\nExecution result:")
    print(json.dumps(result, indent=2, default=str))
    
    print(f"\nEntry Credit: {result.get('entry_credit')}")
    print(f"Margin Required: {result.get('margin_required')}")
    
    # Check the ticket was updated with symbol and prices
    print(f"\nTicket after execution:")
    print(json.dumps(intent.ticket, indent=2))
    
except Exception as e:
    print(f"[ERROR] Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()

print("\n" + "="*70)
