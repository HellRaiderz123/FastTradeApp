"""Test Zerodha credentials validity"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path, override=True)

sys.path.insert(0, 'backend')

try:
    from app.core.broker.zerodha.client import get_kite_client
    
    print("=" * 70)
    print("ZERODHA CREDENTIALS TEST")
    print("=" * 70)
    print()
    
    print("Testing Zerodha API connection...")
    kite = get_kite_client()
    
    try:
        profile = kite.profile()
        print("✅ Zerodha API: CONNECTED")
        print(f"   User ID: {profile.get('user_id')}")
        print(f"   Email: {profile.get('email')}")
        print(f"   Status: {profile.get('status')}")
        print("\n✅ Credentials are VALID and working!")
    except Exception as e:
        print(f"❌ Zerodha API Error: {e}")
        print("\n⚠️  Credentials might be expired or invalid")
        print("   Action: Re-authenticate using: python setup_zerodha_auth.py")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
