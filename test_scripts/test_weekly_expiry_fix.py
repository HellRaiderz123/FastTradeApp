"""
Test script to verify weekly expiry calculation fix.

Ensures:
1. Weekly expiries only (skips monthly)
2. Correct weekdays: NIFTY(Tue), BANKNIFTY(Wed), FINNIFTY(Tue)
3. Skips to next week if today is expiry day
"""

import sys
sys.path.insert(0, 'backend')

from datetime import date, timedelta
from app.core.market.expiry import (
    get_current_weekly_expiry, 
    WEEKLY_EXPIRY_WEEKDAY,
    _is_last_weekday_of_month,
    format_zerodha_expiry
)

def test_weekly_expiry():
    print("=" * 70)
    print("WEEKLY EXPIRY CALCULATION TEST")
    print("=" * 70)
    print(f"\nToday: {date.today()} ({date.today().strftime('%A')})")
    print()
    
    # Test all underlyings
    underlyings = ["NIFTY", "BANKNIFTY", "FINNIFTY"]
    
    for underlying in underlyings:
        print(f"\n{'='*70}")
        print(f"🎯 {underlying}")
        print(f"{'='*70}")
        
        weekday_num = WEEKLY_EXPIRY_WEEKDAY.get(underlying)
        weekday_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"][weekday_num]
        print(f"   Expected weekly expiry day: {weekday_name}")
        
        # Get next weekly expiry
        expiry = get_current_weekly_expiry(underlying)
        expiry_weekday_name = expiry.strftime('%A')
        
        # Check if it's monthly or weekly
        is_monthly = _is_last_weekday_of_month(expiry)
        expiry_type = "MONTHLY" if is_monthly else "WEEKLY"
        
        # Format for Zerodha
        symbol_suffix = format_zerodha_expiry(expiry)
        
        print(f"   Next expiry: {expiry} ({expiry_weekday_name})")
        print(f"   Expiry type: {expiry_type} ✅" if not is_monthly else f"   Expiry type: {expiry_type} ❌ ERROR!")
        print(f"   Zerodha format: {symbol_suffix}")
        print(f"   Days from today: {(expiry - date.today()).days}")
        
        # Verify it's the correct weekday
        if expiry.weekday() == weekday_num:
            print(f"   ✅ Correct weekday!")
        else:
            print(f"   ❌ ERROR: Expected {weekday_name}, got {expiry_weekday_name}!")
        
        # Verify it's not monthly
        if not is_monthly:
            print(f"   ✅ Not a monthly expiry!")
        else:
            print(f"   ❌ ERROR: This is a monthly expiry, should skip to next week!")
        
        # Show next few expiries (simulate by checking upcoming weeks)
        print(f"\n   Next 4 weekly dates ({weekday_name}s):")
        current = date.today()
        for i in range(4):
            # Find next occurrence of this weekday
            days_ahead = (weekday_num - current.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            exp = current + timedelta(days=days_ahead)
            is_monthly_exp = _is_last_weekday_of_month(exp)
            exp_type = "MONTHLY" if is_monthly_exp else "WEEKLY"
            symbol = format_zerodha_expiry(exp)
            marker = "🚫" if is_monthly_exp else "✅"
            print(f"      {i+1}. {exp} ({exp.strftime('%A')}) - {exp_type} - {symbol} {marker}")
            # Move to day after this expiry for next iteration
            current = exp + timedelta(days=1)

if __name__ == "__main__":
    test_weekly_expiry()
    
    print("\n" + "="*70)
    print("✅ TEST COMPLETE")
    print("="*70)
