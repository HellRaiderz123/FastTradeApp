#!/usr/bin/env python3
"""Diagnose why Signal Diagnostics is empty"""
import sys
sys.path.insert(0, 'backend')

from app.db.session import SessionLocal
from app.db.models_signal_outcome import SignalOutcome
from sqlalchemy import func

db = SessionLocal()

print("\n" + "="*80)
print("SIGNAL DIAGNOSTICS DIAGNOSTIC REPORT")
print("="*80)

# Count total records
total = db.query(func.count(SignalOutcome.id)).scalar()
print(f"\n📊 Total SignalOutcome records: {total}")

if total == 0:
    print("   ⚠️ NO RECORDS - Signal outcomes table is empty!")
    print("\n   Possible causes:")
    print("   1. No trades executed yet")
    print("   2. record_entry_snapshot() not being called")
    print("   3. record_exit_outcome() not being called")
else:
    # Count records with entry_time
    with_entry = db.query(func.count(SignalOutcome.id)).filter(SignalOutcome.entry_time.isnot(None)).scalar()
    print(f"   ✅ With entry_time: {with_entry}")
    
    # Count records with exit_time (these show in diagnostics)
    with_exit = db.query(func.count(SignalOutcome.id)).filter(SignalOutcome.exit_time.isnot(None)).scalar()
    print(f"   ✅ With exit_time (SHOWN IN DIAGNOSTICS): {with_exit}")
    print(f"   ⚠️ Without exit_time (NOT SHOWN): {total - with_exit} (still open)")
    
    if with_exit > 0:
        print(f"\n   ✅ GOOD: {with_exit} closed trades found - diagnostics should work!")
    else:
        print(f"\n   ❌ PROBLEM: {total} entry snapshots but NO exit outcomes recorded!")
        print("      → Trades may not be closing properly")
        print("      → record_exit_outcome() may not be called")

# Show sample records
print(f"\n📋 Sample records (first 5):")
print("-"*80)
samples = db.query(SignalOutcome).limit(5).all()
if samples:
    for i, rec in enumerate(samples, 1):
        print(f"\n  [{i}] Intent: {rec.intent_id}")
        print(f"      Underlying: {rec.underlying} | Strategy: {rec.strategy}")
        print(f"      Bias: {rec.signal_bias} | Confidence: {rec.confidence}")
        print(f"      Entry: {rec.entry_time} | Exit: {rec.exit_time}")
        print(f"      P&L: {rec.pnl} ({rec.pnl_pct}%) | Outcome: {rec.outcome}")
else:
    print("  (No records)")

# Show why diagnostics might be empty
print(f"\n🔍 Diagnostics Query Analysis:")
print("-"*80)
closed_trades = db.query(SignalOutcome).filter(SignalOutcome.exit_time.isnot(None)).count()
print(f"   Closed trades (exit_time NOT NULL): {closed_trades}")
if closed_trades == 0:
    print("   ❌ THIS IS WHY DIAGNOSTICS IS EMPTY!")
    print("      The query filters for exit_time.isnot(None)")
    print("      If no trades have closed yet, results are empty")

# Check execution intents table for open trades
print(f"\n🔓 Checking ExecutionIntent table (open trades):")
print("-"*80)
from app.db.models_intent import ExecutionIntent
from app.core.utils.time import now_ist
from datetime import timedelta

open_intents = db.query(ExecutionIntent).filter(ExecutionIntent.status == "EXECUTED").count()
closed_intents = db.query(ExecutionIntent).filter(ExecutionIntent.status == "CLOSED").count()
print(f"   Open positions: {open_intents}")
print(f"   Closed positions: {closed_intents}")

if open_intents > 0:
    print(f"\n   ℹ️ You have {open_intents} OPEN trades")
    print("      Once you close them (manual exit, TP, SL, etc), they'll appear in diagnostics")

db.close()
print("\n" + "="*80)
