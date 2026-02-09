"""
Create weekly auto-strategies for NIFTY, BANKNIFTY, and FINNIFTY.
These strategies will automatically use the next weekly expiry.
"""

import sys
sys.path.insert(0, 'backend')

from app.db.session import SessionLocal
from app.db.models import StrategyConfig
from datetime import datetime

def create_weekly_strategies():
    db = SessionLocal()
    
    try:
        # Define weekly strategies
        strategies = [
            {
                "name": "NIFTY Weekly Spread",
                "description": "Automatic weekly option spread for NIFTY (Tuesday expiry)",
                "strategy_type": "option_spread_15m",
                "underlying": "NIFTY",
                "parameters": {
                    "interval": "15m",
                    "use_ml": True,
                    "min_confidence": 75,
                    "risk_mode": "Conservative",
                    "lots": 1,
                    "capital": 100000,
                    "capital_percent": 10
                },
                "enabled": True
            },
            {
                "name": "BANKNIFTY Weekly Spread",
                "description": "Automatic weekly option spread for BANKNIFTY (Wednesday expiry)",
                "strategy_type": "option_spread_15m",
                "underlying": "BANKNIFTY",
                "parameters": {
                    "interval": "15m",
                    "use_ml": True,
                    "min_confidence": 75,
                    "risk_mode": "Conservative",
                    "lots": 1,
                    "capital": 100000,
                    "capital_percent": 10
                },
                "enabled": True
            },
            {
                "name": "FINNIFTY Weekly Spread",
                "description": "Automatic weekly option spread for FINNIFTY (Tuesday expiry)",
                "strategy_type": "option_spread_15m",
                "underlying": "FINNIFTY",
                "parameters": {
                    "interval": "15m",
                    "use_ml": True,
                    "min_confidence": 75,
                    "risk_mode": "Conservative",
                    "lots": 1,
                    "capital": 100000,
                    "capital_percent": 10
                },
                "enabled": True
            }
        ]
        
        # Check existing and create new ones
        for strat_data in strategies:
            # Check if strategy already exists
            existing = db.query(StrategyConfig).filter_by(
                name=strat_data["name"]
            ).first()
            
            if existing:
                print(f"✅ Strategy already exists: {strat_data['name']} (ID: {existing.id})")
                # Update it
                existing.description = strat_data["description"]
                existing.strategy_type = strat_data["strategy_type"]
                existing.underlying = strat_data["underlying"]
                existing.parameters = strat_data["parameters"]
                existing.enabled = strat_data["enabled"]
                print(f"   Updated to use {strat_data['strategy_type']}")
            else:
                # Create new strategy
                config = StrategyConfig(
                    name=strat_data["name"],
                    description=strat_data["description"],
                    strategy_type=strat_data["strategy_type"],
                    underlying=strat_data["underlying"],
                    parameters=strat_data["parameters"],
                    enabled=strat_data["enabled"],
                    deployed_at=datetime.now() if strat_data["enabled"] else None,
                    created_by="system"
                )
                db.add(config)
                print(f"✅ Created: {strat_data['name']}")
        
        db.commit()
        
        # List all strategies
        print("\n" + "="*70)
        print("ALL CONFIGURED STRATEGIES:")
        print("="*70)
        all_configs = db.query(StrategyConfig).all()
        for c in all_configs:
            status = "🟢 ENABLED" if c.enabled else "🔴 DISABLED"
            print(f"{status} | ID: {c.id:2d} | Type: {c.strategy_type:25s} | {c.underlying:10s} | {c.name}")
        
        print("\n" + "="*70)
        print("✅ WEEKLY STRATEGIES READY!")
        print("="*70)
        print("\nYou can now execute them via:")
        print("1. Web UI: Click 'Execute All Enabled'")
        print("2. API: POST /api/strategies/run/enabled")
        print("\nThese strategies will automatically use:")
        print("- NIFTY: Tuesday weekly expiries")
        print("- BANKNIFTY: Wednesday weekly expiries")
        print("- FINNIFTY: Tuesday weekly expiries")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_weekly_strategies()
