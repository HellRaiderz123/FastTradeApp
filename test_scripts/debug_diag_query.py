#!/usr/bin/env python3
"""Debug the compute_signal_diagnostics query"""
import sys
sys.path.insert(0, 'backend')

from app.db.session import SessionLocal
from app.db.models_signal_outcome import SignalOutcome
from app.core.utils.time import now_ist
from datetime import timedelta

db = SessionLocal()

print("\n" + "="*80)
print("DEBUG: Tracing compute_signal_diagnostics query")
print("="*80)

# Replicate the exact query from compute_signal_diagnostics
limit = 200
lookback_days = 30
underlying = None
strategy = None

print(f"\nParameters:")
print(f"  limit: {limit}")
print(f"  lookback_days: {lookback_days}")
print(f"  underlying: {underlying}")
print(f"  strategy: {strategy}")

# Build query step by step
query = db.query(SignalOutcome).filter(SignalOutcome.exit_time.isnot(None))
print(f"\n[1] Filter by exit_time.isnot(None)")
count1 = query.count()
print(f"    Count: {count1}")

if underlying:
    underlying_str = str(underlying).upper() if underlying else None
    if underlying_str:
        query = query.filter(SignalOutcome.underlying == underlying_str)
        print(f"\n[2] Filter by underlying={underlying_str}")
        count2 = query.count()
        print(f"    Count: {count2}")

if strategy:
    strategy_str = str(strategy).upper() if strategy else None
    if strategy_str:
        query = query.filter(SignalOutcome.strategy == strategy_str)
        print(f"\n[3] Filter by strategy={strategy_str}")
        count3 = query.count()
        print(f"    Count: {count3}")

if lookback_days:
    cutoff = now_ist() - timedelta(days=lookback_days)
    query = query.filter(SignalOutcome.exit_time >= cutoff)
    print(f"\n[4] Filter by exit_time >= {cutoff}")
    count4 = query.count()
    print(f"    Count: {count4}")
    
    # Show which records are excluded
    excluded = db.query(SignalOutcome).filter(
        SignalOutcome.exit_time.isnot(None),
        SignalOutcome.exit_time < cutoff
    ).all()
    if excluded:
        print(f"    ⚠️ Excluded records (older than {lookback_days} days): {len(excluded)}")
        for rec in excluded[:3]:
            print(f"       - {rec.intent_id[:20]}... (exit: {rec.exit_time})")

# Get final rows
rows = query.order_by(SignalOutcome.exit_time.desc()).limit(min(limit, 1000)).all()
print(f"\n[5] Final query result")
print(f"    Returned rows: {len(rows)}")

if rows:
    print(f"\n    First row details:")
    r = rows[0]
    print(f"      Intent ID: {r.intent_id}")
    print(f"      P&L: {r.pnl}")
    print(f"      P&L %: {r.pnl_pct}")
    print(f"      Exit Time: {r.exit_time}")
    print(f"      Outcome: {r.outcome}")

# Now test _aggregate_rows
if rows:
    print(f"\n[6] Testing _aggregate_rows (aggregation function)")
    from app.core.learning.signal_diagnostics import _aggregate_rows
    summary = _aggregate_rows(rows)
    print(f"    Result: {summary}")

db.close()
