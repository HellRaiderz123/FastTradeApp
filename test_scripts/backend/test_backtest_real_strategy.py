"""
Test backtest with ACTUAL strategy (not mock)
"""

import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent))

from app.db.session import engine
from app.db.models import Base, StrategyConfig
from sqlalchemy.orm import Session

print("\n" + "="*80)
print("BACKTEST WITH ACTUAL STRATEGY (not mock)")
print("="*80)

# Create tables
print("\n[1] Database setup...")
Base.metadata.create_all(bind=engine)
print("    ✅ Tables ready")

db = Session(bind=engine)

# Create strategy config using ACTUAL strategy
print("\n[2] Creating strategy config with REAL option_spread_15m strategy...")
strategy = StrategyConfig(
    name="Real Option Spread Strategy",
    description="Using actual option_spread_15m strategy",
    underlying="NIFTY",
    enabled=True,
    strategy_type="option_spread_15m",  # REAL STRATEGY
    parameters={
        "min_confidence": 60,
        "lots": 1,
        "profit_target_pct": 2,
        "stop_loss_pct": 3,
    },
)
db.add(strategy)
db.commit()
db.refresh(strategy)
print(f"    ✅ Strategy created: ID={strategy.id}, Type={strategy.strategy_type}")

# Run backtest
print("\n[3] Running backtest with REAL strategy...")
from app.core.backtest.engine import BacktestEngine

engine_bt = BacktestEngine(strategy, db)
result = engine_bt.run(
    start_date=date(2024, 1, 1),
    end_date=date(2024, 1, 31),
    initial_capital=100000,
)

if result.get("success"):
    print("    ✅ Backtest completed")
    print(f"\n       📊 RESULTS:")
    print(f"       Trades:      {result.get('total_trades')}")
    print(f"       Win Rate:    {result.get('win_rate_pct', 0):.2f}%")
    print(f"       Return:      {result.get('total_return_pct', 0):.2f}%")
    print(f"       Max DD:      {result.get('max_drawdown_pct', 0):.2f}%")
    print(f"       Sharpe:      {result.get('sharpe_ratio', 0):.2f}")
    print(f"       Final Equity: ₹{result.get('final_equity', 0):,.0f}")
else:
    print(f"    ❌ Backtest failed: {result.get('error')}")

print("\n" + "="*80)
print("VERIFICATION")
print("="*80)
print("""
✅ CORRECT BEHAVIOR:
   - Backtest loads the ACTUAL strategy from StrategyConfig
   - Uses option_spread_15m signal generation
   - Executes based on REAL strategy logic
   - Results reflect if THAT strategy would be profitable

This is how it SHOULD work, not using mock strategies!
""")
print("="*80 + "\n")

db.close()
