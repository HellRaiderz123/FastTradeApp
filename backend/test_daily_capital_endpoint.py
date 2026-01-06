#!/usr/bin/env python3
"""
Test the daily capital endpoint
"""
import requests
import json

print("\n" + "="*60)
print("Testing Daily Capital Endpoint")
print("="*60)

try:
    # Test endpoint
    response = requests.get('http://localhost:8000/account/daily-capital?days=30')
    
    print(f"\n✅ Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Response Type: {type(data).__name__}")
        print(f"✅ Records Retrieved: {len(data)}")
        
        if len(data) > 0:
            print(f"\n📊 Sample Record:")
            print(json.dumps(data[0], indent=2))
        else:
            print("\n⚠️  No records in database yet")
            print("   This is normal - capital records will be created when:")
            print("   1. You call GET /account/profile")
            print("   2. You manually POST to /account/daily-capital")
    else:
        print(f"❌ Error: {response.status_code}")
        print(f"   Response: {response.text}")
        
except requests.exceptions.ConnectionError:
    print("\n❌ Error: Cannot connect to backend")
    print("   Make sure uvicorn is running:")
    print("   python -m uvicorn app.main:app --reload")
    
except Exception as e:
    print(f"\n❌ Error: {e}")

print("\n" + "="*60)
