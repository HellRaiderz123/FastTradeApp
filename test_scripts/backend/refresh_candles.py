"""
Force refresh 15m candle data from Zerodha
"""
import sys
sys.path.insert(0, "/app")

from app.db.session import SessionLocal
from app.core.market.candles import fetch_15m_candles
from app.db.models_candles import Candle15m

db = SessionLocal()

print("=" * 70)
print("🔄 REFRESHING 15-MINUTE CANDLE DATA")
print("=" * 70)

# Check current data
current_count = db.query(Candle15m).filter(Candle15m.symbol == "NIFTY").count()
print(f"Current candles in DB: {current_count}")

# Get latest timestamp
latest = (
    db.query(Candle15m)
    .filter(Candle15m.symbol == "NIFTY")
    .order_by(Candle15m.timestamp.desc())
    .first()
)

if latest:
    print(f"Latest candle: {latest.timestamp}")
    print()

# Fetch fresh data (default 15 days)
print("📥 Fetching latest 15 days of candles from Zerodha...")
try:
    fetch_15m_candles(db, "NIFTY", days=15)
    print("✅ Refresh complete!")
    print()
    
    # Check new count
    new_count = db.query(Candle15m).filter(Candle15m.symbol == "NIFTY").count()
    print(f"Total candles in DB now: {new_count}")
    print(f"Added: {new_count - current_count} new candles")
    
    # Show new latest
    latest = (
        db.query(Candle15m)
        .filter(Candle15m.symbol == "NIFTY")
        .order_by(Candle15m.timestamp.desc())
        .first()
    )
    print(f"Latest candle now: {latest.timestamp}")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

db.close()
print()
print("=" * 70)
print("✅ Now restart backend and test signal generation")
print("=" * 70)
