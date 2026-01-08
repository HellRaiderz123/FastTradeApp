"""
Test MTM calculation for the executed trade
"""
from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent
from app.core.execution.zerodha import ZerodhaExecutionAdapter
from app.core.broker.zerodha.client import get_kite_client
from datetime import date

db = SessionLocal()

today = date.today()

# Get the executed intent
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
    print("Testing MTM Calculation")
    print("="*60)
    print(f"Strategy: {intent.strategy}")
    print(f"Entry Credit: ₹{intent.entry_credit:,.2f}")
    
    # Test MTM calculation
    try:
        kite = get_kite_client()
        executor = ZerodhaExecutionAdapter(kite_client=kite, dry_run=True)
        
        print("\n📊 Calculating current MTM...")
        pnl = executor.mtm(intent)
        
        print(f"\n✅ Current P&L: ₹{pnl:,.2f}")
        
        if pnl > 0:
            print(f"   🟢 Profit: ₹{pnl:,.2f}")
        elif pnl < 0:
            print(f"   🔴 Loss: ₹{abs(pnl):,.2f}")
        else:
            print(f"   ⚪ Breakeven")
        
        # Update the intent
        intent.pnl = pnl
        intent.unrealized_pnl = pnl
        from app.core.utils.time import now_ist
        intent.last_mtm_at = now_ist()
        db.commit()
        
        print(f"\n✅ Updated intent with current P&L")
        print(f"   Last MTM at: {intent.last_mtm_at}")
        
    except Exception as e:
        print(f"\n❌ MTM calculation failed: {e}")
        import traceback
        traceback.print_exc()
else:
    print("No executed trades found")

db.close()
