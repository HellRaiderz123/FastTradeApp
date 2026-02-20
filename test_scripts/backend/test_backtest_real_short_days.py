"""Run a short backtest on *real* candles for option_spread_15m.

This is meant as a quick sanity check for a few days (not a full options P&L backtest).
It runs option_spread_15m in BACKTEST_MODE (signal-only; no live Zerodha option-chain calls).

Usage (PowerShell):
  cd backend
  $env:BACKTEST_MODE="1"; $env:SAVE_CANDLES_TO_DB="0"; python test_backtest_real_short_days.py
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.orm import Session

# Load backend/.env
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=False)

# Make the run deterministic / correct-er for backtest
os.environ.setdefault("BACKTEST_MODE", "1")
os.environ.setdefault("SAVE_CANDLES_TO_DB", "0")

from app.db.session import engine
from app.db.models import Base, StrategyConfig
from app.core.backtest.engine import BacktestEngine

Base.metadata.create_all(bind=engine)

db = Session(bind=engine)

try:
    # Get or create a real strategy config
    strategy = (
        db.query(StrategyConfig)
        .filter(StrategyConfig.strategy_type == "option_spread_15m")
        .order_by(StrategyConfig.id.asc())
        .first()
    )

    if not strategy:
        strategy = StrategyConfig(
            name="Backtest Option Spread 15m",
            description="Short backtest (signal-only)",
            underlying="NIFTY",
            enabled=True,
            strategy_type="option_spread_15m",
            parameters={
                "min_confidence": 60,
                "lots": 1,
                "risk_mode": "Conservative",
                "capital": 100000,
            },
        )
        db.add(strategy)
        db.commit()
        db.refresh(strategy)

    # Make sure backtest can actually generate signals
    params = dict(strategy.parameters or {})
    params["min_confidence"] = 0
    params["use_ml"] = False
    strategy.parameters = params
    strategy.enabled = True
    db.commit()

    # Few trading days window (override with BT_START/BT_END as YYYY-MM-DD)
    end_date = date.today() - timedelta(days=2)
    start_date = end_date - timedelta(days=7)

    bt_start = os.getenv("BT_START")
    bt_end = os.getenv("BT_END")
    if bt_start:
        start_date = datetime.strptime(bt_start, "%Y-%m-%d").date()
    if bt_end:
        end_date = datetime.strptime(bt_end, "%Y-%m-%d").date()

    print("=" * 80)
    print("SHORT REAL-CANDLE BACKTEST (option_spread_15m, BACKTEST_MODE=1)")
    print("=" * 80)
    print(f"Strategy ID: {strategy.id} ({strategy.underlying})")
    print(f"Range: {start_date} -> {end_date}")
    print("Running backtest...")

    engine_bt = BacktestEngine(strategy, db)
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

    # Helpful sanity
    eq = result.get("equity_curve") or []
    print(f"Equity points (days): {len(eq)}")
    if result.get("candles_loaded") is not None:
        print(f"Candles loaded: {result.get('candles_loaded')}")
    if result.get("signal_counts") is not None:
        print(f"Signal counts: {result.get('signal_counts')}")
    if result.get("raw_action_counts") is not None:
        print(f"Raw action counts: {result.get('raw_action_counts')}")

    trades = result.get("trades") or []
    buys = sum(1 for t in trades if t.get("strategy") == "BUY")
    sells = sum(1 for t in trades if t.get("strategy") == "SELL")
    print(f"\nTrades by side: BUY={buys}, SELL={sells}, TOTAL={len(trades)}")

finally:
    db.close()
