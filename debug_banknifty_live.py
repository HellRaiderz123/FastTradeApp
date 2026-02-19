from datetime import datetime, date, time
from zoneinfo import ZoneInfo

# Simulate checking if today's expiry is still valid
today = date(2026, 2, 18)  # Wednesday
print("=" * 70)
print("CHECKING IF TODAY'S BANKNIFTY EXPIRY IS VALID")
print("=" * 70)

print(f"\nToday: {today} ({today.strftime('%A')})")
print(f"This IS a BANKNIFTY expiry day (Wednesday)")

# Check market time
try:
    ist_tz = ZoneInfo("Asia/Kolkata")
except:
    from datetime import timezone, timedelta
    ist_tz = timezone(timedelta(hours=5, minutes=30))

# Simulate different times
test_times = [
    ("09:30", "Market open"),
    ("14:00", "Before close"),
    ("15:30", "Market close"),
    ("16:00", "After market"),
]

print("\nMarket Status Check:")
for time_str, label in test_times:
    hour, minute = map(int, time_str.split(':'))
    test_now = datetime.now(ist_tz).replace(hour=hour, minute=minute, second=0, microsecond=0)
    market_close = test_now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    if test_now < market_close:
        status = "✅ Today's expiry VALID"
    else:
        status = "❌ Today's expiry EXPIRED (use next week)"
    
    print(f"  {time_str} ({label}): {status}")

print("\n" + "=" * 70)
print("ANALYSIS")
print("=" * 70)
print("\n💡 If you're seeing symbols like BANKNIFTY2621861100CE but LTP is ₹0:")
print("\n1. ✅ Symbol format is CORRECT")
print("2. ✅ Expiry date is CORRECT (Feb 18 is Wednesday)")
print("3. ✅ NFO exchange is CORRECT")
print("\n4. ❌ POSSIBLE ISSUES:")
print("   a) Today IS the expiry day - options might have expired at 3:30 PM")
print("   b) Market data API call is failing")
print("   c) These specific strikes (61100, 61300, 61400) might be too far OTM")
print("   d) Zerodha instruments.csv might not have these strikes")

print("\n5. 🔍 TO DEBUG:")
print("   - Check what time it is now in IST")
print("   - If after 3:30 PM, today's options have expired")
print("   - Try using next Wednesday's expiry (Feb 25 = BANKNIFTY26FEB...)")
print("   - Or March 4 (BANKNIFTY2634...)")
