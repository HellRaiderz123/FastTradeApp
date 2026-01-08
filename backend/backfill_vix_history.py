"""
Backfill 52-week VIX history for IV Rank calculation
"""
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)

from app.db.session import SessionLocal, Base, engine
from app.core.market.zerodha_historic_fetcher import initialize_vix_historic_data
from app.db.models import VixHistoric

print("=" * 80)
print("BACKFILL 52-WEEK VIX HISTORY")
print("=" * 80)

# Create tables if needed
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# Check current state
existing = db.query(VixHistoric).count()
print(f"\n📊 Current VIX records in DB: {existing}")

if existing > 0:
    latest = db.query(VixHistoric).order_by(VixHistoric.trade_date.desc()).first()
    earliest = db.query(VixHistoric).order_by(VixHistoric.trade_date.asc()).first()
    print(f"   Date range: {earliest.trade_date} to {latest.trade_date}")
    print(f"   Latest VIX: {latest.india_vix}, IV Rank: {latest.iv_rank}")

# Initialize/backfill
print("\n🔄 Initializing VIX historic data (365 days)...")
success = initialize_vix_historic_data(db, initial_days=365)

if success:
    print("\n✅ VIX history backfilled successfully!")
    
    # Show updated state
    new_count = db.query(VixHistoric).count()
    print(f"\n📊 Total VIX records now: {new_count}")
    
    latest = db.query(VixHistoric).order_by(VixHistoric.trade_date.desc()).first()
    if latest:
        print(f"   Latest: {latest.trade_date}")
        print(f"   VIX: {latest.india_vix}")
        print(f"   IV Rank: {latest.iv_rank}%")
        print(f"   52w High: {latest.vix_52w_high}, Low: {latest.vix_52w_low}")
else:
    print("\n⚠️ Could not backfill from Zerodha API")
    print("   This may happen if historical data API is unavailable")
    print("   IV Rank will be calculated once daily VIX updates accumulate")

db.close()

print("\n" + "=" * 80)
print("DONE")
print("=" * 80)
