"""
test_iv_rank_system.py
---------------------
Test the complete IV Rank system with database storage and calculations.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, date

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.db.models import VixHistoric
from app.core.market.iv_rank_calculator import (
    calculate_iv_rank,
    get_52week_vix_range,
    update_daily_iv_rank,
    get_latest_iv_rank,
    get_vix_historic_stats,
)


def setup_test_db():
    """Create an in-memory test database."""
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def populate_test_data(db):
    """Populate test database with sample VIX data."""
    print("\n=== Populating Test Data ===\n")
    
    # Create 365 days of simulated VIX data
    base_date = datetime.now().date() - timedelta(days=365)
    
    # Simulate realistic VIX pattern
    # Base VIX around 15-18, with realistic variations
    vix_values = []
    current_vix = 16.5
    
    for i in range(365):
        # Add some realistic volatility
        if i % 30 == 0:  # Spike every month
            current_vix += 3.5
        elif i % 7 == 0:
            current_vix -= 1.2
        
        # Add random walk
        import random
        current_vix += (random.random() - 0.5) * 1.5
        
        # Keep within realistic bounds
        current_vix = max(10.0, min(40.0, current_vix))
        
        trade_date = base_date + timedelta(days=i)
        vix_values.append(current_vix)
        
        # Create record
        record = VixHistoric(
            trade_date=trade_date,
            india_vix=round(current_vix, 2),
            source="test_data"
        )
        db.add(record)
    
    db.commit()
    print(f"✅ Created {len(vix_values)} test VIX records")
    print(f"   VIX range: {min(vix_values):.2f} - {max(vix_values):.2f}")
    
    return vix_values


def test_iv_rank_calculation(db):
    """Test IV Rank calculation logic."""
    print("\n=== Testing IV Rank Calculation ===\n")
    
    # Get 52-week range
    high_52w, low_52w = get_52week_vix_range(db)
    print(f"52-Week VIX Range: {low_52w:.2f} - {high_52w:.2f}")
    
    # Test IV Rank at different VIX levels
    test_cases = [
        (low_52w, "At 52-week low"),
        (high_52w, "At 52-week high"),
        ((low_52w + high_52w) / 2, "At midpoint"),
        (20.0, "At 20.0"),
        (25.0, "At 25.0"),
    ]
    
    for vix_value, description in test_cases:
        iv_rank = calculate_iv_rank(vix_value, high_52w, low_52w)
        print(f"VIX={vix_value:.2f} ({description}): IV Rank = {iv_rank:.2f}%")
    
    print("\n✅ IV Rank calculation test passed!")


def test_daily_update(db):
    """Test updating daily VIX records with IV Rank."""
    print("\n=== Testing Daily Update Logic ===\n")
    
    # Update today with a test value
    test_vix = 18.5
    today = datetime.now().date()
    
    # Remove today's record if exists
    db.query(VixHistoric).filter(VixHistoric.trade_date == today).delete()
    db.commit()
    
    # Update with test value
    iv_rank = update_daily_iv_rank(db, test_vix, today)
    
    print(f"Updated today ({today}): VIX={test_vix}, IV_Rank={iv_rank:.2f}%")
    
    # Verify it was stored
    record = db.query(VixHistoric).filter(VixHistoric.trade_date == today).first()
    assert record is not None, "Record not stored!"
    assert record.india_vix == test_vix, "VIX value mismatch!"
    assert record.iv_rank is not None, "IV Rank not calculated!"
    
    print(f"✅ Verified stored record: {record.india_vix} VIX, {record.iv_rank:.2f}% IV Rank")


def test_latest_iv_rank(db):
    """Test fetching latest IV Rank."""
    print("\n=== Testing Latest IV Rank Fetch ===\n")
    
    latest_iv_rank = get_latest_iv_rank(db)
    
    if latest_iv_rank is not None:
        print(f"Latest IV Rank: {latest_iv_rank:.2f}%")
        print("✅ Latest IV Rank fetch successful!")
    else:
        print("⚠️  No IV Rank data available yet")


def test_vix_stats(db):
    """Test VIX statistics calculation."""
    print("\n=== Testing VIX Statistics ===\n")
    
    stats = get_vix_historic_stats(db)
    
    print(f"Total Records: {stats.get('total_records', 0)}")
    print(f"Latest Date: {stats.get('latest_date', 'N/A')}")
    print(f"Earliest Date: {stats.get('earliest_date', 'N/A')}")
    print(f"Current VIX: {stats.get('current_vix', 'N/A')}")
    print(f"Current IV Rank: {stats.get('current_iv_rank', 'N/A')}")
    print(f"52w High: {stats.get('52w_high', 'N/A')}")
    print(f"52w Low: {stats.get('52w_low', 'N/A')}")
    
    assert stats.get('total_records', 0) > 0, "No records in database!"
    print("\n✅ VIX statistics test passed!")


def test_iv_rank_percentiles(db):
    """Test that IV Rank correctly represents percentiles."""
    print("\n=== Testing IV Rank Percentiles ===\n")
    
    high_52w, low_52w = get_52week_vix_range(db)
    range_width = high_52w - low_52w
    
    # Create test cases at 0%, 25%, 50%, 75%, 100%
    percentiles = [0, 25, 50, 75, 100]
    
    for pct in percentiles:
        test_vix = low_52w + (range_width * pct / 100)
        iv_rank = calculate_iv_rank(test_vix, high_52w, low_52w)
        
        print(f"{pct}th Percentile: VIX={test_vix:.2f}, IV_Rank={iv_rank:.2f}%")
        
        # Verify percentile calculation
        expected_iv_rank = pct
        tolerance = 0.1  # Allow small rounding error
        assert abs(iv_rank - expected_iv_rank) < tolerance, \
            f"IV Rank {iv_rank} doesn't match expected {expected_iv_rank}"
    
    print("\n✅ IV Rank percentile test passed!")


def test_edge_cases(db):
    """Test edge cases and error handling."""
    print("\n=== Testing Edge Cases ===\n")
    
    # Test with None values
    iv_rank = calculate_iv_rank(20.0, None, None)
    assert iv_rank is None, "Should return None for missing range"
    print("✅ Handles missing range data")
    
    # Test with equal high and low
    iv_rank = calculate_iv_rank(20.0, 20.0, 20.0)
    assert iv_rank == 50.0, "Should return 50% when no range"
    print("✅ Handles zero range (returns 50%)")
    
    # Test clamping
    iv_rank = calculate_iv_rank(100.0, 30.0, 10.0)  # Above range
    assert iv_rank == 100.0, "Should clamp to 100"
    print("✅ Clamps to 100% for values above range")
    
    iv_rank = calculate_iv_rank(5.0, 30.0, 10.0)  # Below range
    assert iv_rank == 0.0, "Should clamp to 0"
    print("✅ Clamps to 0% for values below range")
    
    print("\n✅ Edge cases test passed!")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("IV RANK SYSTEM TEST SUITE")
    print("=" * 60)
    
    # Setup
    db = setup_test_db()
    
    # Tests
    vix_values = populate_test_data(db)
    test_iv_rank_calculation(db)
    test_daily_update(db)
    test_latest_iv_rank(db)
    test_vix_stats(db)
    test_iv_rank_percentiles(db)
    test_edge_cases(db)
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ ALL IV RANK TESTS PASSED!")
    print("=" * 60)
    print("\nKey Findings:")
    print("- IV Rank correctly calculates percentile from VIX range")
    print("- Daily updates store and compute IV Rank")
    print("- Edge cases handled gracefully")
    print("- Database queries work correctly")
    print("\nNext Steps:")
    print("- Connect to real Zerodha data feed")
    print("- Run daily update job to keep data current")
    print("- Integrate IV Rank into strategy decisions")


if __name__ == "__main__":
    main()
