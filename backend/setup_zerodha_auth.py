"""
Zerodha Authentication Setup Helper
====================================

This script helps you:
1. Get your Zerodha API credentials
2. Generate access token
3. Test the connection
4. Save credentials to environment

Run: python setup_zerodha_auth.py
"""

import os
import sys
from datetime import datetime, timedelta

print("\n" + "="*60)
print("ZERODHA AUTHENTICATION SETUP")
print("="*60)

print("\n📋 Step 1: Get Your API Key")
print("-" * 60)
print("1. Go to: https://kite.trade/")
print("2. Login with your Zerodha credentials")
print("3. Go to 'My Apps' section")
print("4. Create a new app (or use existing)")
print("5. Note down the API_KEY and API_SECRET")

api_key = input("\n🔑 Enter your ZERODHA_API_KEY: ").strip()
api_secret = input("🔒 Enter your ZERODHA_API_SECRET: ").strip()

if not api_key or not api_secret:
    print("\n❌ API Key and Secret are required!")
    sys.exit(1)

print("\n📋 Step 2: Generate Access Token")
print("-" * 60)
print("We'll help you generate an access token...")

try:
    from kiteconnect import KiteConnect
    
    kite = KiteConnect(api_key=api_key)
    
    # Generate login URL
    login_url = kite.login_url()
    print(f"\n🌐 Open this URL in your browser:\n{login_url}")
    print("\n📝 After login, you'll be redirected to a URL like:")
    print("   http://127.0.0.1/?request_token=XXXXXX&action=login&status=success")
    
    request_token = input("\n🎫 Paste the request_token from URL: ").strip()
    
    if not request_token:
        print("\n❌ Request token is required!")
        sys.exit(1)
    
    # Generate session
    print("\n⏳ Generating access token...")
    data = kite.generate_session(request_token, api_secret=api_secret)
    access_token = data["access_token"]
    user_id = data.get("user_id", "unknown")
    
    print(f"\n✅ Access Token Generated Successfully!")
    print(f"   User ID: {user_id}")
    print(f"   Access Token: {access_token[:20]}...{access_token[-10:]}")
    
    # Test connection
    print("\n🧪 Testing connection...")
    kite.set_access_token(access_token)
    profile = kite.profile()
    print(f"✅ Connection successful!")
    print(f"   Name: {profile.get('user_name')}")
    print(f"   Email: {profile.get('email')}")
    print(f"   Broker: {profile.get('broker')}")
    
    # Save to .env file
    print("\n💾 Saving credentials...")
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    
    with open(env_path, "w") as f:
        f.write(f"# Zerodha KiteConnect Credentials\n")
        f.write(f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Valid until: ~{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"ZERODHA_API_KEY={api_key}\n")
        f.write(f"ZERODHA_API_SECRET={api_secret}\n")
        f.write(f"ZERODHA_ACCESS_TOKEN={access_token}\n\n")
        f.write(f"# Database\n")
        f.write(f"DATABASE_URL=sqlite:///./fasttrade.db\n\n")
        f.write(f"# Server\n")
        f.write(f"DEBUG=True\n")
    
    print(f"✅ Credentials saved to: {env_path}")
    
    # Set environment variables for current session
    os.environ["ZERODHA_API_KEY"] = api_key
    os.environ["ZERODHA_ACCESS_TOKEN"] = access_token
    
    print("\n" + "="*60)
    print("✅ SETUP COMPLETE!")
    print("="*60)
    print("\n📝 Next Steps:")
    print("1. Restart your FastAPI server")
    print("2. The WebSocket will now fetch real prices")
    print("\n⚠️  Note: Access token expires daily at 6:00 AM")
    print("   You'll need to re-run this script each day")
    
except ImportError:
    print("\n❌ kiteconnect module not installed!")
    print("   Run: pip install kiteconnect")
    sys.exit(1)
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
