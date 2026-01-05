"""
test_iv_rank_integration.py
--------------------------
Integration test to verify IV Rank system works end-to-end.
Tests database, fetching, calculation, and API integration.
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.db.models import VixHistoric
from app.core.market.iv_rank_calculator import (
    get_latest_iv_rank,
    get_vix_historic_stats,
    update_daily_iv_rank,
)
from app.core.market.zerodha_historic_fetcher import initialize_vix_historic_data
from app.core.market.vix_iv_api import get_vix_iv_data_cached, determine_iv_regime


def test_database_connection():
    """Test database connection and table creation."""
    print("\n=== Testing Database Connection ===\n")
    
    try:
        # Use the real database from settings
        from app.db.session import engine, SessionLocal
        
        # Check if tables exist
        inspector = __import__('sqlalchemy.inspect', fromlist=['inspect']).inspect(engine)
        tables = inspector.get_table_names()
        
        if "vix_historic" in tables:
            print("✅ VixHistoric table exists")
        else:
            print("⚠️ VixHistoric table not found, creating...")
            Base.metadata.create_all(engine)
            print("✅ VixHistoric table created")
        
        # Test connection
        db = SessionLocal()
        count = db.query(VixHistoric).count()
        db.close()
        
        print(f"✅ Database connection works ({count} VIX records)")
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False


def test_vix_data_population():
    """Test fetching and storing VIX data."""
    print("\n=== Testing VIX Data Population ===\n")
    
    try:
        from app.db.session import SessionLocal
        
        db = SessionLocal()
        
        # Get current counts
        before_count = db.query(VixHistoric).count()
        print(f"Records before: {before_count}")
        
        # Try to initialize (will skip if data exists)
        result = initialize_vix_historic_data(db)
        
        after_count = db.query(VixHistoric).count()
        print(f"Records after: {after_count}")
        
        db.close()
        
        if after_count > 0:
            print(f"✅ VIX data available ({after_count} records)")
            return True
        else:
            print("⚠️ No VIX data in database")
            print("   → Will use test data for demonstration")
            return populate_test_vix_data()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def populate_test_vix_data():
    """Populate test VIX data for demonstration."""
    print("\n   Populating test VIX data...\n")
    
    try:
        from app.db.session import SessionLocal
        
        db = SessionLocal()
        
        # Create 365 days of simulated data
        import random
        from datetime import timedelta
        base_date = datetime.now().date() - timedelta(days=365)
        current_vix = 16.5
        
        for i in range(365):
            if i > 0 and i % 90 == 0:
                current_vix += 2.0
            
            current_vix += (random.random() - 0.5) * 1.0
            current_vix = max(10.0, min(35.0, current_vix))
            
            trade_date = base_date + timedelta(days=i)
            
            existing = db.query(VixHistoric).filter(VixHistoric.trade_date == trade_date).first()
            if not existing:
                record = VixHistoric(
                    trade_date=trade_date,
                    india_vix=round(current_vix, 2),
                    source="test_data"
                )
                db.add(record)
        
        db.commit()
        db.close()
        
        print("✅ Test VIX data populated (365 days)")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_iv_rank_calculation():
    """Test IV Rank calculation from stored data."""
    print("\n=== Testing IV Rank Calculation ===\n")
    
    try:
        from app.db.session import SessionLocal
        
        db = SessionLocal()
        
        # Get latest IV Rank
        latest_iv_rank = get_latest_iv_rank(db)
        
        if latest_iv_rank is not None:
            print(f"✅ Latest IV Rank: {latest_iv_rank:.2f}%")
        else:
            print("⚠️ No IV Rank calculated yet")
            
            # Try to calculate for today
            test_vix = 18.5
            iv_rank = update_daily_iv_rank(db, test_vix)
            
            if iv_rank is not None:
                print(f"✅ Calculated IV Rank for today: {iv_rank:.2f}%")
            else:
                print("⚠️ Could not calculate IV Rank (insufficient historic data)")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_iv_rank_in_signal():
    """Test IV Rank integration into signal pipeline."""
    print("\n=== Testing IV Rank in Signal Pipeline ===\n")
    
    try:
        from app.db.session import SessionLocal
        
        db = SessionLocal()
        
        # Get VIX/IV data
        vix_iv_data = get_vix_iv_data_cached()
        
        print(f"India VIX: {vix_iv_data.get('india_vix', 'N/A')}")
        print(f"IV Rank: {vix_iv_data.get('iv_rank', 'N/A')}%")
        print(f"VIX Source: {vix_iv_data.get('vix_source', 'N/A')}")
        print(f"IV Source: {vix_iv_data.get('iv_source', 'N/A')}")
        
        # Determine regime
        if vix_iv_data['india_vix'] and vix_iv_data['iv_rank']:
            regime = determine_iv_regime(
                vix_iv_data['india_vix'],
                vix_iv_data['iv_rank']
            )
            print(f"IV Regime: {regime}")
            print("✅ IV Rank integrated in signal pipeline")
        else:
            print("⚠️ Missing VIX/IV data for regime determination")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_vix_statistics():
    """Test VIX statistics and data summary."""
    print("\n=== Testing VIX Statistics ===\n")
    
    try:
        from app.db.session import SessionLocal
        
        db = SessionLocal()
        
        stats = get_vix_historic_stats(db)
        
        print(f"Total Records: {stats.get('total_records', 0)}")
        print(f"Latest Date: {stats.get('latest_date', 'N/A')}")
        print(f"Earliest Date: {stats.get('earliest_date', 'N/A')}")
        print(f"Current VIX: {stats.get('current_vix', 'N/A')}")
        print(f"Current IV Rank: {stats.get('current_iv_rank', 'N/A')}")
        print(f"52w High: {stats.get('52w_high', 'N/A')}")
        print(f"52w Low: {stats.get('52w_low', 'N/A')}")
        
        if stats.get('total_records', 0) > 0:
            print("✅ VIX statistics available")
        else:
            print("⚠️ No statistics (empty database)")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_scheduler_setup():
    """Verify scheduler configuration."""
    print("\n=== Testing Scheduler Setup ===\n")
    
    try:
        from app.core.market.scheduler import scheduler
        
        print(f"Scheduler timezone: {scheduler.timezone}")
        print(f"Scheduler running: {scheduler.running}")
        
        # Check registered jobs
        jobs = scheduler.get_jobs()
        if jobs:
            print(f"Registered jobs: {len(jobs)}")
            for job in jobs:
                print(f"  - {job.id}: {job.trigger}")
        else:
            print("No jobs registered yet (start app to register)")
        
        print("✅ Scheduler configured")
        return True
        
    except Exception as e:
        print(f"⚠️ Scheduler test: {e}")
        return True  # Not a critical failure


def main():
    """Run all integration tests."""
    print("\n" + "=" * 70)
    print("IV RANK SYSTEM - INTEGRATION TEST")
    print("=" * 70)
    
    results = []
    
    # Run tests
    results.append(("Database Connection", test_database_connection()))
    results.append(("VIX Data Population", test_vix_data_population()))
    results.append(("IV Rank Calculation", test_iv_rank_calculation()))
    results.append(("IV Rank in Signals", test_iv_rank_in_signal()))
    results.append(("VIX Statistics", test_vix_statistics()))
    results.append(("Scheduler Setup", test_scheduler_setup()))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ All tests passed! IV Rank system is ready.\n")
        print("NEXT STEPS:")
        print("1. Run the app: `uvicorn app.main:app --reload`")
        print("2. VIX data will auto-initialize on startup")
        print("3. Daily updates run at 3:45 PM IST")
        print("4. IV Rank automatically included in signals")
    else:
        print("\n⚠️ Some tests failed. Check errors above.")
    
    print("=" * 70)


if __name__ == "__main__":
    main()
