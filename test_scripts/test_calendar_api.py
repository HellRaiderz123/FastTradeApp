#!/usr/bin/env python
"""Quick test of the calendar API"""
import requests
import json

try:
    # Test calendar/today endpoint
    print("Testing /calendar/today...")
    r = requests.get('http://localhost:8000/calendar/today', timeout=10)
    print(f"Status: {r.status_code}")
    
    data = r.json()
    print(f"Response keys: {list(data.keys())}")
    print(f"Total events: {len(data.get('events', []))}")
    
    if data.get('events'):
        event = data['events'][0]
        print(f"\nFirst event:")
        print(f"  Title: {event.get('title')}")
        print(f"  Type: {event.get('type')}")
        print(f"  Date: {event.get('date')}")
        print(f"  Impact: {event.get('impact')}")
        print(f"  Countdown: {event.get('countdown', 'MISSING')}")
        print(f"  Days until: {event.get('days_until', 'MISSING')}")
    else:
        print("No events returned")
    
    print(f"\nData source: {data.get('data_source')}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
