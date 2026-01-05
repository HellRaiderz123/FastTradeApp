"""Test full signal generation including spot, atm, strike_meta"""
import sys
sys.path.insert(0, "/app")

from app.core.strategies.option_spread_15m.engine import run_option_spread
from app.db.session import SessionLocal

db = SessionLocal()

payload = {
    "underlying": "NIFTY",
    "capital": 500000,
    "lots": 1,
    "risk_mode": "Conservative",
    "min_confidence": 60
}

print("=" * 70)
print("✅ RUNNING FULL OPTION SPREAD ENGINE")
print("=" * 70)
print()

try:
    result = run_option_spread(db, payload)
    
    print(f"Strategy:  {result['strategy']}")
    print(f"Approved:  {result['approved']}")
    print(f"Reason:    {result['reason']}")
    print()
    
    if result.get('spot'):
        print(f"Spot:      {result['spot']}")
    else:
        print(f"Spot:      ❌ NULL")
        
    if result.get('atm'):
        print(f"ATM:       {result['atm']}")
    else:
        print(f"ATM:       ❌ NULL")
        
    if result.get('strike_meta'):
        print(f"Strike Meta: {result['strike_meta']}")
    else:
        print(f"Strike Meta: ❌ NULL")
    
    print()
    
    # Show signal indicators
    sig = result.get('signal', {})
    indicators = sig.get('indicators', {})
    
    print("Signal Indicators:")
    print(f"  ADX:      {indicators.get('adx')} (quality: {'✅ PASS' if indicators.get('adx', 0) >= 25 else '❌ FAIL'})")
    print(f"  RSI:      {indicators.get('rsi')} (bias: {sig.get('bias')})")
    print(f"  Quality:  {sig.get('quality_score')}/8")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

db.close()
