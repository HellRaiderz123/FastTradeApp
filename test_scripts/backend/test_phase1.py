"""
Phase 1 Test: Verify StrategyRegistry and API endpoints
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.core.strategies.registry import StrategyRegistry
from app.db.session import SessionLocal
from app.db.models import StrategyConfig

def test_registry():
    """Test StrategyRegistry"""
    print("\n🧪 Testing StrategyRegistry...")
    
    strategies = StrategyRegistry.list_all()
    print(f"✅ Registered strategies: {strategies}")
    
    # Try to get a strategy
    try:
        strategy_class = StrategyRegistry.get('option_spread_15m')
        print(f"✅ Got strategy class: {strategy_class}")
    except Exception as e:
        print(f"❌ Error getting strategy: {e}")
        return False
    
    return True


def test_database():
    """Test StrategyConfig table"""
    print("\n🧪 Testing StrategyConfig table...")
    
    db = SessionLocal()
    try:
        # Try to query the table (should be empty)
        configs = db.query(StrategyConfig).all()
        print(f"✅ Table exists and is queryable. Current configs: {len(configs)}")
        
        # Try to create a test config
        test_config = StrategyConfig(
            name="test_config_phase1",
            description="Test config for Phase 1",
            strategy_type="option_spread_15m",
            underlying="NIFTY",
            parameters={"risk_mode": "BALANCED", "lots": 1},
            enabled=False,
            created_by="phase1_test"
        )
        
        db.add(test_config)
        db.commit()
        print(f"✅ Successfully created test config (ID: {test_config.id})")
        
        # Query it back
        retrieved = db.query(StrategyConfig).filter(StrategyConfig.name == "test_config_phase1").first()
        print(f"✅ Successfully retrieved config: {retrieved.name}")
        
        # Clean up
        db.delete(retrieved)
        db.commit()
        print(f"✅ Test config deleted")
        
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("PHASE 1 IMPLEMENTATION TEST")
    print("=" * 60)
    
    registry_ok = test_registry()
    database_ok = test_database()
    
    print("\n" + "=" * 60)
    if registry_ok and database_ok:
        print("✅ PHASE 1 TESTS PASSED")
        print("=" * 60)
        exit(0)
    else:
        print("❌ PHASE 1 TESTS FAILED")
        print("=" * 60)
        exit(1)
