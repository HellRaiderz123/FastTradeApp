"""
Check if database has fresh NIFTY candles
"""
import sys
sys.path.insert(0, "/app")

from app.db.session import SessionLocal
from app.db.models_candles import Candle15m
from datetime import datetime

db = SessionLocal()

# Get total count
total = db.query(Candle15m).filter(Candle15m.symbol == "NIFTY").count()

# Get latest 10
latest = (
    db.query(Candle15m)
    .filter(Candle15m.symbol == "NIFTY")
    .order_by(Candle15m.timestamp.desc())
    .limit(10)
    .all()
)

print("=" * 70)
print("NIFTY CANDLE DATABASE STATUS")
print("=" * 70)
print()
print(f"Total NIFTY candles: {total}")
print()
print("Latest 10 candles:")
print("-" * 70)
print(f"{'Timestamp':<25} {'Close':<12} {'Volume':<15}")
print("-" * 70)

for c in latest:
    print(f"{str(c.timestamp):<25} {c.close:<12.2f} {c.volume:<15.0f}")

print()

if len(latest) > 0:
    latest_ts = latest[0].timestamp
    now = datetime.now()
    age_minutes = (now - latest_ts).total_seconds() / 60
    print(f"Latest candle: {latest_ts}")
    print(f"Age: {age_minutes:.0f} minutes ago")
    
    if age_minutes < 30:
        print("✅ Data is FRESH (< 30 mins)")
    elif age_minutes < 60:
        print("⚠️  Data is RECENT (< 60 mins)")
    else:
        print("❌ Data is STALE (> 60 mins)")

db.close()
