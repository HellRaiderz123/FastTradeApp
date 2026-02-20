#!/usr/bin/env python
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from current directory
env_path = Path(".env")
print(f"Looking for .env at: {env_path.absolute()}")
print(f"File exists: {env_path.exists()}")

load_dotenv(dotenv_path=env_path, override=True)

api_key = os.getenv("ZERODHA_API_KEY", "NOT SET")
access_token = os.getenv("ZERODHA_ACCESS_TOKEN", "NOT SET")

print(f"\nZERODHA_API_KEY: {api_key}")
print(f"ZERODHA_ACCESS_TOKEN: {access_token}")

# Test if kite client can initialize
try:
    from app.core.broker.zerodha.client import get_kite_client
    print("\nTesting kite client initialization...")
    kite = get_kite_client()
    print("✅ Kite client initialized successfully!")
    
    # Try to get profile
    profile = kite.profile()
    print(f"\n✅ Account Profile: {profile.get('user_id')}")
    
    # Try to get margins
    margins = kite.margins()
    capital = margins["equity"]["available"]
    print(f"✅ Available Capital: ₹{capital}")
    
    # Test the account API endpoint
    print("\n\nTesting /account/profile endpoint...")
    from app.api.routes.account import get_account_profile
    result = get_account_profile()
    print("✅ Account Profile Response:")
    import json
    print(json.dumps(result, indent=2))
    
except Exception as e:
    import traceback
    print(f"❌ Error: {e}")
    traceback.print_exc()
