"""Options-accurate backtest for option_spread_15m.

This backtest prices each option leg using Zerodha historical option candles.
It is materially more accurate than the existing directional proxy backtest.

Important:
- Requires valid Zerodha credentials/access token (.env) because it calls
  `kite.historical_data()` for option contracts.
- Works best for very recent date ranges (current expiry). Older expiries may not
  exist in the *current* instruments dump, so token resolution can fail.

Usage (PowerShell):
  cd backend
  $env:BT_START="2026-01-06"; $env:BT_END="2026-01-07"; .\.venv\Scripts\python.exe test_backtest_options_spread_15m.py

  # If you want to force a specific range:
  $env:BT_START="2026-01-01"; $env:BT_END="2026-01-07"; .\.venv\Scripts\python.exe test_backtest_options_spread_15m.py
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.orm import Session

# Load backend/.env
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=False)

from app.db.session import engine
from app.db.models import Base, StrategyConfig
from app.core.backtest.options_engine import OptionsBacktestEngine

Base.metadata.create_all(bind=engine)

db = Session(bind=engine)


def _parse_date(env_key: str) -> date | None:
    v = os.getenv(env_key)
    if not v:
        return None
    return datetime.strptime(v, "%Y-%m-%d").date()


try:
    strategy = (
        db.query(StrategyConfig)
        .filter(StrategyConfig.strategy_type == "option_spread_15m")
        .order_by(StrategyConfig.id.asc())
        .first()
    )

    if not strategy:
        strategy = StrategyConfig(
            name="Options Backtest Option Spread 15m",
            description="Options-accurate backtest (leg pricing)",
            underlying="NIFTY",
            enabled=True,
            strategy_type="option_spread_15m",
            parameters={
                "min_confidence": 75,
                "lots": 1,
                "risk_mode": "Conservative",
                "capital": 100000,
            },
        )
        db.add(strategy)
        db.commit()
        db.refresh(strategy)

    # Default: last 2 trading days
    end_date = _parse_date("BT_END") or (date.today() - timedelta(days=1))
    start_date = _parse_date("BT_START") or (end_date - timedelta(days=2))

    print("=" * 80)
    print("OPTIONS-AWARE BACKTEST (option_spread_15m, Zerodha option candles)")
    print("=" * 80)
    print(f"Strategy ID: {strategy.id} ({strategy.underlying})")
    print(f"Range: {start_date} -> {end_date}")

    engine_bt = OptionsBacktestEngine(strategy, db)
    result = engine_bt.run(start_date=start_date, end_date=end_date, initial_capital=100000)

    if not result.get("success"):
        raise SystemExit(f"Backtest failed: {result.get('error')}")

    print("\nRESULTS")
    print(f"Trades:        {result.get('total_trades')}")
    print(f"Win Rate:      {result.get('win_rate_pct'):.2f}%")
    print(f"Return:        {result.get('total_return_pct'):.2f}%")
    print(f"Max DD:        {result.get('max_drawdown_pct'):.2f}%")
    print(f"Sharpe:        {result.get('sharpe_ratio'):.2f}")
    print(f"Final Equity:  ₹{result.get('final_equity'):,.2f}")
    print(f"Candles loaded: {result.get('candles_loaded')}")
    print(f"Signal counts:  {result.get('signal_counts')}")

    trades = result.get("trades") or []
    if trades:
        last = trades[-1]
        print("\nLAST TRADE")
        print(f"{last.get('strategy')} pnl={last.get('pnl')} qty={last.get('qty')}")
        for leg in last.get("legs") or []:
            print(f"  {leg.get('side')} {leg.get('symbol')}")

finally:
    db.close()
