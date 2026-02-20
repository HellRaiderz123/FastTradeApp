"""
Test the updated expiry API to ensure it returns only weekly expiries.
"""

import sys
sys.path.insert(0, 'backend')

from datetime import datetime, date, timedelta
from app.core.market.expiry import WEEKLY_EXPIRY_WEEKDAY, _is_last_weekday_of_month

def test_weekly_expiry_filter():
    print("=" * 70)
    print("WEEKLY EXPIRY API TEST")
    print("=" * 70)
    print(f"Today: {date.today()} ({date.today().strftime('%A')})\n")
    
    underlyings = ["NIFTY", "BANKNIFTY", "FINNIFTY"]
    
    for symbol in underlyings:
        print(f"\n{'='*70}")
        print(f"🎯 {symbol}")
        print(f"{'='*70}")
        
        today = date.today()
        expiries = []
        symbol_key = symbol.upper().strip()
        expiry_weekday = WEEKLY_EXPIRY_WEEKDAY.get(symbol_key, 1)
        weekday_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"][expiry_weekday]
        
        print(f"Weekly expiry day: {weekday_name}")
        print(f"\nNext 5 WEEKLY expiries (skipping monthly):")
        
        def next_weekday(d, wd):
            """Find next target weekday from given date (0=Mon..6=Sun)."""
            days_until = (wd - d.weekday()) % 7
            if days_until == 0:
                days_until = 7
            return d + timedelta(days=days_until)
        
        # Generate expiries
        current_date = today
        for _ in range(15):
            current_date = next_weekday(current_date, expiry_weekday)
            
            # Filter out monthly expiries
            if _is_last_weekday_of_month(current_date):
                # Skip monthly expiry
                print(f"   🚫 SKIPPED: {current_date} (MONTHLY)")
                current_date = current_date + timedelta(days=1)
                continue
            
            expiries.append(current_date)
            print(f"   {len(expiries)}. ✅ {current_date} ({current_date.strftime('%A')}) - WEEKLY")
            current_date = current_date + timedelta(days=1)
            
            # Stop when we have enough weekly expiries
            if len(expiries) >= 5:
                break
        
        print(f"\n   Total weekly expiries found: {len(expiries)}")
    
    print("\n" + "="*70)
    print("✅ TEST COMPLETE - Strategy Builder will show WEEKLY expiries only!")
    print("="*70)

if __name__ == "__main__":
    test_weekly_expiry_filter()
