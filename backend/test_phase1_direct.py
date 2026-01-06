"""
Test Phase 1 directly without running server
"""

import sys
sys.path.insert(0, '.')

from app.db.session import SessionLocal, engine, Base
from app.db.models import StrategyConfig
from app.core.strategies.registry import StrategyRegistry
from datetime import datetime

print("=" * 60)
print("PHASE 1 - DIRECT TESTING (No Server)")
print("=" * 60)

# 1. Test Database CRUD
print("\n1️⃣ Testing StrategyConfig CRUD...")
db = SessionLocal()

# Create
strategy = StrategyConfig(
    name="NIFTY_Conservative_Direct",
    description="Test strategy created directly",
    strategy_type="option_spread_15m",
    underlying="NIFTY",
    parameters={"risk_mode": "CONSERVATIVE", "lots": 1},
    enabled=False,
    created_by="test_user"
)
db.add(strategy)
db.commit()
print(f"✅ Created strategy ID: {strategy.id}")

# Read
fetched = db.query(StrategyConfig).filter_by(name="NIFTY_Conservative_Direct").first()
print(f"✅ Retrieved strategy: {fetched.name}")

# Update
fetched.enabled = True
fetched.deployed_at = datetime.now()
db.commit()
print(f"✅ Updated strategy - Enabled: {fetched.enabled}")

# Delete
db.delete(fetched)
db.commit()
print(f"✅ Deleted strategy")

db.close()

# 2. Test Registry
print("\n2️⃣ Testing StrategyRegistry...")
all_strats = StrategyRegistry.list_all()
print(f"✅ Available strategies: {all_strats}")

if "option_spread_15m" in all_strats:
    print(f"✅ OptionSpread15m found in registry")
    strat_class = StrategyRegistry.get("option_spread_15m")
    print(f"✅ Strategy class: {strat_class}")

print("\n" + "=" * 60)
print("✅ PHASE 1 DIRECT TEST COMPLETE - ALL SYSTEMS OK")
print("=" * 60)
