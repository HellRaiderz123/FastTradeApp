#!/usr/bin/env python3
"""Backfill signal diagnostics for existing strategy runs"""
import sqlite3
from app.db.session import SessionLocal
from app.db.models import StrategyRun
from app.db.models_signal_outcome import SignalOutcome
from app.core.utils.time import now_ist
import json

db = SessionLocal()

print("=" * 70)
print("BACKFILLING SIGNAL DIAGNOSTICS")
print("=" * 70)

# Get all strategy runs
runs = db.query(StrategyRun).all()
print(f"\n📋 Found {len(runs)} strategy runs")

backfilled = 0
already_recorded = 0
failed = 0

for run in runs:
    intent_id = f"strategy_run_{run.id}"
    
    # Check if already recorded
    existing = (
        db.query(SignalOutcome)
        .filter(SignalOutcome.intent_id == intent_id)
        .first()
    )
    
    if existing:
        already_recorded += 1
        continue
    
    try:
        sig = run.signal or {}
        ctx = run.context or {}
        
        outcome = SignalOutcome(
            intent_id=intent_id,
            run_id=run.id,
            underlying=run.underlying or "UNKNOWN",
            strategy=run.strategy or "UNKNOWN",
            signal_strength=str(sig.get("signal") or sig.get("recommendation") or "UNKNOWN"),
            signal_bias=str(sig.get("bias") or "UNKNOWN"),
            confidence=float(sig.get("confidence") or 0),
            market_mode=str(ctx.get("market_mode") or "UNKNOWN"),
            iv_regime=str(ctx.get("iv_regime") or "UNKNOWN"),
            signal_json=sig if sig else None,
            context_json=ctx if ctx else None,
            entry_time=run.created_at,
            exit_time=None,
            exit_reason=None,
            pnl=run.pnl,
            pnl_pct=None,
            created_at=run.created_at,
        )
        
        db.add(outcome)
        db.commit()
        backfilled += 1
        print(f"  ✅ Run {run.id}: {run.strategy} on {run.underlying}")
        
    except Exception as e:
        failed += 1
        print(f"  ❌ Run {run.id}: {e}")

print(f"\n{'=' * 70}")
print(f"📊 BACKFILL RESULTS:")
print(f"  ✅ Backfilled: {backfilled}")
print(f"  ℹ️  Already recorded: {already_recorded}")
print(f"  ❌ Failed: {failed}")
print(f"{'=' * 70}")

db.close()
