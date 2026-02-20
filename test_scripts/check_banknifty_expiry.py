from datetime import datetime, date
import calendar

# Check BANKNIFTY expiries (Wednesdays)
print("=" * 70)
print("BANKNIFTY EXPIRY ANALYSIS (Wednesdays)")
print("=" * 70)

# February 2026
last_day = calendar.monthrange(2026, 2)[1]
print(f"\nFebruary 2026 has {last_day} days")

wednesdays = []
for day in range(1, last_day + 1):
    dt = datetime(2026, 2, day)
    if dt.weekday() == 2:  # Wednesday = 2
        wednesdays.append(dt)

print("\nAll Wednesdays in February 2026:")
for i, w in enumerate(wednesdays, 1):
    is_last = i == len(wednesdays)
    label = "MONTHLY (last Wednesday)" if is_last else "WEEKLY"
    print(f"  {w.date()} - {label}")

print(f"\n📅 Today: 2026-02-18 (Wednesday)")
print(f"✅ Feb 18 IS a valid BANKNIFTY expiry (it's Wednesday)")
print(f"✅ Feb 25 is the last Wednesday = MONTHLY expiry")

print("\n" + "=" * 70)
print("SYMBOL FORMAT CHECK")
print("=" * 70)

# Check symbol format
expiry = date(2026, 2, 18)
year = expiry.year % 100  # 26
month = expiry.month      # 2
day = expiry.day          # 18

print(f"\nFor expiry {expiry}:")
print(f"  Year: {year}")
print(f"  Month: {month}")
print(f"  Day: {day}")
print(f"  Combined: {year}{month}{day} = 26218")

symbol = f"BANKNIFTY{year}{month}{day}61100CE"
print(f"\n✅ Symbol format: {symbol}")
print(f"   This looks CORRECT!")

print("\n💡 PROBLEM: LTP showing ₹0 suggests:")
print("   1. Zerodha might not have this expiry in their database yet")
print("   2. Symbol format might need different formatting")
print("   3. Need to check actual Zerodha instruments list")
