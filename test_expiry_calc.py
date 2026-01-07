#!/usr/bin/env python3
"""Test expiry date calculation"""

from datetime import date, timedelta

today = date(2026, 1, 7)
print(f"Today: {today} ({today.strftime('%A')})")
print(f"Today weekday (0=Mon, 3=Thu): {today.weekday()}")

def next_thursday(d):
    days = (1 - d.weekday()) % 7  # Changed from 3 (Thursday) to 1 (Tuesday)
    if days == 0:
        days = 7
    return d + timedelta(days=days)

# Get 5 Thursdays
print("\nExpiry dates:")
expiries = []
current = today
for i in range(5):
    current = next_thursday(current)
    expiries.append(current.strftime("%Y-%m-%d"))
    days_away = (current - today).days
    print(f"  {i+1}. {current.strftime('%Y-%m-%d')} ({current.strftime('%A')}) - {days_away} days away")

print(f"\nExpiries list: {expiries}")
