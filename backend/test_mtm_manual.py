"""
Test MTM calculation with real LTP from Zerodha
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent
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
    print("Testing MTM Calculation (Mock)")
    print("="*60)
    print(f"Strategy: {intent.strategy}")
    print(f"Entry Credit: ₹{intent.entry_credit:,.2f}")
    print(f"\nLegs:")
    for leg in intent.ticket["legs"]:
        print(f"  {leg['side']:4} {leg['strike']} {leg['type']} - {leg['symbol']}")
    
    # Mock LTP calculation (simulate current market prices)
    from app.core.market.ltp import get_ltp
    
    ticket = intent.ticket
    qty = ticket["lot_size"] * ticket["lots"]
    symbols = [leg["symbol"] for leg in ticket["legs"]]
    
    print(f"\n📊 Fetching current LTP for {len(symbols)} symbols...")
    try:
        ltp_map = get_ltp(symbols)
        
        print(f"\nCurrent Market Prices:")
        for sym, price in ltp_map.items():
            print(f"  {sym}: ₹{price:.2f}")
        
        # Calculate MTM using entry_credit method
        entry_credit = intent.entry_credit or 0.0
        cost_to_close = 0.0
        
        for leg in ticket["legs"]:
            sym = leg["symbol"]
            ltp = float(ltp_map.get(sym, 0.0))
            
            if leg["side"] == "SELL":
                cost_to_close += ltp * qty
            else:
                cost_to_close -= ltp * qty
        
        pnl = entry_credit - cost_to_close
        
        print(f"\n💰 P&L Calculation:")
        print(f"   Entry Credit:    ₹{entry_credit:,.2f}")
        print(f"   Cost to Close:   ₹{cost_to_close:,.2f}")
        print(f"   ─────────────────────────────")
        print(f"   Current P&L:     ₹{pnl:,.2f}")
        
        if pnl > 0:
            pct = (pnl / entry_credit) * 100 if entry_credit else 0
            print(f"   Status: 🟢 PROFIT (+{pct:.1f}%)")
        elif pnl < 0:
            pct = (abs(pnl) / entry_credit) * 100 if entry_credit else 0
            print(f"   Status: 🔴 LOSS (-{pct:.1f}%)")
        else:
            print(f"   Status: ⚪ BREAKEVEN")
        
        # Update the intent
        intent.pnl = pnl
        intent.unrealized_pnl = pnl
        from app.core.utils.time import now_ist
        intent.last_mtm_at = now_ist()
        db.commit()
        
        print(f"\n✅ Updated database with current P&L")
        print(f"   Last MTM: {intent.last_mtm_at}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
else:
    print("No executed trades found")

db.close()
