"""
Quick test of backtest with mock strategy
"""
import os

from pathlib import Path
from dotenv import load_dotenv

# Load backend/.env if present (do not overwrite current env)
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=False)

# Keep prior behavior if user hasn't configured execution mode
os.environ.setdefault("EXECUTION_MODE", "ZERODHA_DRY_RUN")

from datetime import date, timedelta
from app.db.session import SessionLocal
from app.db.models import StrategyConfig
from app.core.backtest.engine import BacktestEngine

# Create DB session
db = SessionLocal()

try:
    # Get or create a strategy config for testing
    strategy = db.query(StrategyConfig).filter(
        StrategyConfig.strategy_type == "option_spread_15m"
    ).first()
    
    if not strategy:
        print("[!] No strategy config found, creating test one...")
        strategy = StrategyConfig(
            name="Test Strategy",
            strategy_type="option_spread_15m",
            underlying="NIFTY",
            parameters={"lots": 1, "min_confidence": 60},
            enabled=True,
        )
        db.add(strategy)
        db.commit()
        print(f"[OK] Created strategy with ID: {strategy.id}")
    
    # Run backtest
    print(f"\n[*] Running 1-week backtest ({strategy.name})...")
    end_date = date.today()
    start_date = end_date - timedelta(days=7)
    
    engine = BacktestEngine(strategy, db)
    results = engine.run(start_date, end_date, initial_capital=100000)
    
    print(f"\n{'='*80}")
    print("BACKTEST RESULTS")
    print(f"{'='*80}")
    print(f"Success: {results.get('success')}")
    print(f"Total Trades: {results.get('total_trades')}")
    print(f"Final Equity: {results.get('final_equity', 0):,.0f}")
    print(f"Total Return: {results.get('total_return_pct', 0):.2f}%")
    print(f"Sharpe Ratio: {results.get('sharpe_ratio', 0):.2f}")
    print(f"Win Rate: {results.get('win_rate_pct', 0):.1f}%")
    
    if results.get('total_trades', 0) > 0:
        print(f"\n[OK] BACKTEST SUCCESSFUL - Generated {results['total_trades']} trades")
    else:
        print(f"\n[!] No trades generated - check signal logic")
        
    # Show first few trades
    trades = results.get('trades', [])
    if trades:
        print(f"\nFirst 5 trades:")
        for i, trade in enumerate(trades[:5], 1):
            print(f"  {i}. {trade['entry_date']} -> {trade['exit_date']}: P&L = {trade['pnl']:.0f}")

finally:
    db.close()

print("\n[OK] Test complete")
