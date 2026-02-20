from datetime import datetime
import calendar

# Check February 2026 Tuesdays
last_day = calendar.monthrange(2026, 2)[1]
print(f"February 2026 has {last_day} days\n")

tuesdays = []
for day in range(1, last_day + 1):
    date = datetime(2026, 2, day)
    if date.weekday() == 1:  # Tuesday
        tuesdays.append(date)
        
print("All Tuesdays in February 2026:")
for i, t in enumerate(tuesdays, 1):
    is_last = i == len(tuesdays)
    label = "MONTHLY (last Tuesday)" if is_last else "WEEKLY"
    print(f"  {t.date()} - {label}")

print(f"\nToday: 2026-02-18 (Wednesday)")
print(f"Last Tuesday was: {tuesdays[-2].date()} (Feb 17)")
print(f"Next Tuesday is: {tuesdays[-1].date()} (Feb 24) - THIS IS MONTHLY")
print(f"\nSince Feb 24 is monthly, the code skips it!")
print(f"Next WEEKLY expiry after Feb 24: 2026-03-03 (first Tuesday of March)")
