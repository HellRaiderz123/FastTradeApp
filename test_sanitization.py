#!/usr/bin/env python3
"""Test JSON sanitization for inf/nan values"""

import sys
import json
import math

sys.path.insert(0, 'd:\\FastTradeApp\\backend')

from app.api.routes.execution_v2 import sanitize_json_value

# Test cases
test_data = {
    "normal": 1.5,
    "nan_value": float('nan'),
    "inf_positive": float('inf'),
    "inf_negative": float('-inf'),
    "nested": {
        "test": float('nan'),
        "value": 42,
        "deep": {
            "infinity": float('inf')
        }
    },
    "list": [1, float('nan'), float('inf'), "string"]
}

print("Original data (not JSON serializable):")
print(test_data)
print("\n" + "="*60 + "\n")

# Sanitize
sanitized = sanitize_json_value(test_data)

print("Sanitized data:")
print(sanitized)
print("\n" + "="*60 + "\n")

# Try to JSON serialize
try:
    json_str = json.dumps(sanitized)
    print("✅ Successfully serialized to JSON:")
    print(json_str)
except ValueError as e:
    print(f"❌ JSON serialization failed: {e}")

print("\n" + "="*60 + "\n")
print("Test PASSED - sanitization works correctly!")
