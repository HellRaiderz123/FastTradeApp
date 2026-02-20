#!/usr/bin/env python3
"""Test strategy execution endpoint with sanitization"""

import requests
import json

BASE_URL = "http://localhost:8000"

# Test execute single strategy endpoint
print("Testing /strategies/run/single endpoint...\n")

payload = {
    "strategy_id": 1,
    "additional_context": {}
}

print(f"Payload: {json.dumps(payload, indent=2)}\n")

try:
    response = requests.post(
        f"{BASE_URL}/strategies/run/single",
        json=payload,
        timeout=30
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Headers: {dict(response.headers)}\n")
    
    if response.status_code == 200:
        print("✅ SUCCESS - Strategy executed without JSON serialization error!")
        result = response.json()
        print(f"\nResponse keys: {list(result.keys())}")
        print(f"\nFull response (truncated):")
        # Pretty print with truncation
        response_str = json.dumps(result, indent=2)
        if len(response_str) > 1000:
            print(response_str[:1000] + "\n... (truncated)")
        else:
            print(response_str)
    else:
        print(f"❌ ERROR - Status {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
except json.JSONDecodeError as e:
    print(f"❌ JSON Decode Error: {e}")
    print(f"Response text: {response.text[:500]}")
except requests.exceptions.RequestException as e:
    print(f"❌ Request Error: {e}")
except Exception as e:
    print(f"❌ Unexpected Error: {e}")
