"""Fix symbols in old positions to correct Zerodha format"""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path, override=True)

sys.path.insert(0, 'backend')

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent
from app.core.broker.zerodha_symbols import build_zerodha_option_symbol
from app.core.utils.time import now_ist
from datetime import date

print("="*70)
print("FIXING SYMBOLS IN OLD POSITIONS")
print("="*70)
print()

db = SessionLocal()
try:
    intents = (
        db.query(ExecutionIntent)
        .filter(ExecutionIntent.status.in_(['EXECUTED', 'CLOSED']))
        .all()
    )
    
    print(f"Found {len(intents)} active positions\n")
    
    for intent in intents:
        print(f"Processing: {intent.intent_id[:8]}")
        
        # Skip if no expiry
        if not intent.expiry:
            print(f"  [SKIP - no expiry]\n")
            continue
        
        # Parse expiry if it's a string
        try:
            if isinstance(intent.expiry, str):
                expiry_date = date.fromisoformat(intent.expiry)
            else:
                expiry_date = intent.expiry
        except (ValueError, TypeError):
            print(f"  [SKIP - invalid expiry: {intent.expiry}]\n")
            continue
        
        ticket = intent.ticket or {}
        
        # Fix each leg's symbol
        updated = False
        for leg in ticket.get("legs", []):
            old_symbol = leg.get("symbol")
            
            # Rebuild the symbol with correct format
            new_symbol = build_zerodha_option_symbol(
                underlying=intent.underlying,
                expiry=expiry_date,
                strike=int(leg["strike"]),
                option_type=str(leg["type"]),
            )
            
            if old_symbol != new_symbol:
                print(f"  {old_symbol} -> {new_symbol}")
                leg["symbol"] = new_symbol
                updated = True
        
        if updated:
            # Reassign to mark JSON field as dirty for SQLAlchemy
            intent.ticket = dict(ticket)
            db.commit()
            print(f"  [UPDATED and saved]\n")
        else:
            print(f"  [NO CHANGES]\n")
    
    print("="*70)
    print("SYMBOLS FIXED")
    print("="*70)
    
except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
