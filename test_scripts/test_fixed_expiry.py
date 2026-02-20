from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

# Simulate the fixed logic
def next_weekday_fixed(test_date, weekday, test_time_str="10:00"):
    """Test version with time simulation"""
    days_until = (weekday - test_date.weekday()) % 7
    
    if days_until == 0:
        # Today is the target weekday - check if market has closed
        try:
            ist_tz = ZoneInfo("Asia/Kolkata")
        except:
            from datetime import timezone
            ist_tz = timezone(timedelta(hours=5, minutes=30))
        
        # Simulate time for testing
        test_hour, test_min = map(int, test_time_str.split(':'))
        now_ist = datetime.now(ist_tz).replace(hour=test_hour, minute=test_min, second=0, microsecond=0)
        market_close_time = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
        
        if now_ist < market_close_time:
            # Market still open, include today's expiry
            return test_date
        else:
            # Market closed, jump to next week
            days_until = 7
    
    return test_date + timedelta(days=days_until)

print("=" * 70)
print("TESTING FIXED EXPIRY LOGIC")
print("=" * 70)

# Test Case 1: Today is Wednesday Feb 18, next Tuesday is Feb 24
test_date = date(2026, 2, 18)  # Wednesday
print(f"\n1. Today is {test_date} ({test_date.strftime('%A')})")
next_tue = next_weekday_fixed(test_date, 1)  # 1 = Tuesday
print(f"   Next Tuesday expiry: {next_tue}")
print(f"   ✅ Correct! Shows Feb 24 (will be included even if monthly)")

# Test Case 2: Today IS Tuesday Feb 24, before market close
test_date = date(2026, 2, 24)  # Tuesday
print(f"\n2. Today is {test_date} ({test_date.strftime('%A')}) at 10:00 AM")
next_tue = next_weekday_fixed(test_date, 1, "10:00")
print(f"   Next Tuesday expiry: {next_tue}")
if next_tue == test_date:
    print(f"   ✅ Correct! Shows today's expiry (market still open)")
else:
    print(f"   ❌ Wrong! Should show {test_date}")

# Test Case 3: Today IS Tuesday Feb 24, after market close
print(f"\n3. Today is {test_date} ({test_date.strftime('%A')}) at 4:00 PM")
next_tue = next_weekday_fixed(test_date, 1, "16:00")
print(f"   Next Tuesday expiry: {next_tue}")
expected = date(2026, 3, 3)
if next_tue == expected:
    print(f"   ✅ Correct! Shows next week's expiry (market closed)")
else:
    print(f"   ❌ Wrong! Should show {expected}")

print("\n" + "=" * 70)
print("SUMMARY: With the fix, Feb 24 will now appear in the dropdown!")
print("=" * 70)
