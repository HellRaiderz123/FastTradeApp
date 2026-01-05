#!/usr/bin/env python3
"""Test the account profile API to verify capital calculation fix."""

import requests
import json
import time

# Give the server time to start
time.sleep(2)

try:
    response = requests.get('http://localhost:8000/account/profile', timeout=5)
    response.raise_for_status()
    
    data = response.json()
    print("✅ API Response:")
    print(json.dumps(data, indent=2))
    
    # Check the fix
    capital = data.get('capital')
    print(f"\n💰 Capital: ₹{capital}")
    
    if capital == 99999:
        print("✅ CORRECT: Capital is ₹99999 (not doubled)")
    elif capital == 199998:
        print("❌ FAILED: Capital is still doubled (₹199998)")
    else:
        print(f"⚠️ UNEXPECTED: Capital is ₹{capital}")
        
except requests.exceptions.ConnectionError:
    print("❌ Could not connect to backend on http://localhost:8000")
    print("Make sure the server is running: uvicorn app.main:app --port 8000 --host 0.0.0.0")
except Exception as e:
    print(f"❌ Error: {e}")
