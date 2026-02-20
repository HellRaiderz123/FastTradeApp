from datetime import datetime, date, timedelta

# Test the expiry logic
today = date(2026, 2, 18)  # Wednesday
print(f"Testing with today = {today} ({today.strftime('%A')})\n")

# Test next_weekday function from market.py
def next_weekday(d, weekday):
    """Find next target weekday from given date (0=Mon..6=Sun)."""
    days_until = (weekday - d.weekday()) % 7
    if days_until == 0:
        days_until = 7  # Skip to next week if today is the target day
    return d + timedelta(days=days_until)

# NIFTY expires on Tuesday (weekday 1)
expiry_weekday = 1  # Tuesday

next_exp = next_weekday(today, expiry_weekday)
print(f"Next Tuesday from {today}: {next_exp}")
print(f"This gives us: {next_exp} which is Feb 24 (monthly, gets skipped)")
print(f"\nThat's why users see March 3rd as the first option!")

print("\n" + "="*60)
print("Testing if TODAY was Tuesday (Feb 24):")
print("="*60)
feb_24 = date(2026, 2, 24)
next_from_24 = next_weekday(feb_24, expiry_weekday)
print(f"If today is {feb_24} (Tuesday), next_weekday returns: {next_from_24}")
print(f"This skips the current day's expiry even if market hasn't closed!")
