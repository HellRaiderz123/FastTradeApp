"""
One-time migration: create condition_strategies + condition_strategy_backtests tables
and import existing data from condition_strategies.json.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from app.db.session import engine, Base
from app.db.models_condition_strategy import ConditionStrategy, ConditionStrategyBacktest
from app.db.session import SessionLocal

# Create tables
Base.metadata.create_all(bind=engine, tables=[
    ConditionStrategy.__table__,
    ConditionStrategyBacktest.__table__,
])
print("Tables created (or already exist).")

# Load existing JSON
JSON_FILE = os.path.join(os.path.dirname(__file__), "app", "data", "condition_strategies.json")
if not os.path.exists(JSON_FILE):
    print("No condition_strategies.json found — nothing to migrate.")
    sys.exit(0)

with open(JSON_FILE) as f:
    strategies = json.load(f)

print(f"Found {len(strategies)} strategies in JSON file.")

db = SessionLocal()
migrated = 0
skipped = 0

for s in strategies:
    existing = db.query(ConditionStrategy).filter_by(name=s["name"]).first()
    if existing:
        print(f"  SKIP  '{s['name']}' (already in DB)")
        skipped += 1
        continue

    backtest_id = None
    backtest_result = s.get("last_backtest_result")
    if backtest_result:
        bt = ConditionStrategyBacktest(
            strategy_id=s["id"],
            strategy_name=s["name"],
            start_date=backtest_result.get("start_date", ""),
            end_date=backtest_result.get("end_date", ""),
            initial_capital=backtest_result.get("initial_capital", 100000.0),
            final_capital=backtest_result.get("final_capital"),
            result=backtest_result,
        )
        db.add(bt)
        db.flush()
        backtest_id = bt.id

    row = ConditionStrategy(
        name=s["name"],
        description=s.get("description", ""),
        strategy_type=s.get("strategy_type", "Equity Swing"),
        direction=s.get("direction", "BUY"),
        timeframe=s.get("timeframe", "1 Hour"),
        universe=s.get("universe", "NIFTY50"),
        instruments=s.get("instruments", []),
        entry_conditions=s.get("entry_conditions", []),
        exit_config=s.get("exit_config", {}),
        is_active=s.get("is_active", True),
        auto_scan_enabled=s.get("auto_scan_enabled", False),
        auto_amount=s.get("auto_amount", 10000.0),
        last_signal_count=s.get("last_signal_count", 0),
        last_backtest_id=backtest_id,
    )
    db.add(row)
    migrated += 1
    print(f"  OK    '{s['name']}' (backtest={'yes' if backtest_id else 'no'})")

db.commit()
db.close()
print(f"\nDone. Migrated: {migrated}, Skipped: {skipped}")
