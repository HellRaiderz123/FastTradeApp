"""
Check the execution mode and intent data for MTM tracking
"""
from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent
from datetime import date
import json

db = SessionLocal()

today = date.today()

# Get the executed intent from today
intent = (
    db.query(ExecutionIntent)
    .filter(
        ExecutionIntent.created_at >= today,
        ExecutionIntent.executed == True
    )
    .order_by(ExecutionIntent.created_at.desc())
    .first()
)

if intent:
    print("="*60)
    print("Executed Trade Details")
    print("="*60)
    print(f"Intent ID: {intent.intent_id}")
    print(f"Strategy: {intent.strategy}")
    print(f"Status: {intent.status}")
    print(f"Executed: {intent.executed}")
    print(f"Entry Credit: {intent.entry_credit}")
    print(f"PnL: {intent.pnl}")
    print(f"Last MTM: {intent.last_mtm_at}")
    
    print(f"\n📦 Execution Result:")
    if intent.execution_result:
        print(json.dumps(intent.execution_result, indent=2))
    else:
        print("   None")
    
    print(f"\n🎫 Ticket:")
    print(json.dumps(intent.ticket, indent=2))
    
    print("\n" + "="*60)
    print("Checking MTM Requirements:")
    print("="*60)
    
    # Check if legs have symbol
    legs = intent.ticket.get("legs", [])
    for i, leg in enumerate(legs):
        has_symbol = "symbol" in leg
        has_price = "price" in leg
        print(f"Leg {i+1}: symbol={has_symbol}, price={has_price}")
        if has_symbol:
            print(f"  Symbol: {leg['symbol']}")
        if has_price:
            print(f"  Price: {leg['price']}")
    
    # Check execution mode
    if intent.execution_result:
        mode = intent.execution_result.get("mode")
        print(f"\nExecution Mode: {mode}")
        
        if mode == "ZERODHA_DRY_RUN":
            print("⚠️  Mode is ZERODHA_DRY_RUN")
            print("   WebSocket filters for mode='PAPER' only!")
            print("   This is why MTM isn't updating!")
    
else:
    print("No executed trades found today")

db.close()
