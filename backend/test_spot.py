"""
Test get_spot() function to see why it's failing
"""
import sys
sys.path.insert(0, "/app")

print("=" * 70)
print("Testing spot price fetching")
print("=" * 70)
print()

try:
    from app.core.market.spot import get_spot
    print("✅ Successfully imported get_spot")
    print()
    
    try:
        spot = get_spot("NIFTY")
        print(f"✅ Got NIFTY spot: {spot}")
    except Exception as e:
        print(f"❌ Error getting spot: {type(e).__name__}: {e}")
        print()
        print("Root cause:")
        import traceback
        traceback.print_exc()
        
except Exception as e:
    print(f"❌ Import error: {e}")
    import traceback
    traceback.print_exc()
