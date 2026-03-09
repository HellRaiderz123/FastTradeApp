#!/usr/bin/env python3
"""Check why closed trades don't have exit outcomes"""
import sys
sys.path.insert(0, 'backend')

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent
from app.db.models_signal_outcome import SignalOutcome

db = SessionLocal()

print("\n" + "="*80)
print("CLOSED TRADES ANALYSIS - Exit Outcome Recording Issue")
print("="*80)

# Get closed trades
closed = db.query(ExecutionIntent).filter(ExecutionIntent.status == "CLOSED").all()
print(f"\nClosed ExecutionIntent records: {len(closed)}")

for i, intent in enumerate(closed[:5], 1):
    print(f"\n  [{i}] {intent.intent_id}")
    print(f"      Status: {intent.status}")
    print(f"      Closed at: {intent.closed_at}")
    print(f"      P&L: {intent.pnl}")
    
    # Check if SignalOutcome exists
    signal_outcome = db.query(SignalOutcome).filter(
        SignalOutcome.intent_id == intent.intent_id
    ).first()
    
    if signal_outcome:
        print(f"      ✅ SignalOutcome found")
        print(f"         Exit time: {signal_outcome.exit_time}")
        print(f"         P&L: {signal_outcome.pnl}")
        print(f"         Outcome: {signal_outcome.outcome}")
    else:
        print(f"      ❌ NO SignalOutcome record for this intent!")
        print(f"         → record_exit_outcome() was never called OR failed")

print("\n" + "="*80)
print("CONCLUSION:")
print("="*80)

# Count mismatch
closed_intents = db.query(ExecutionIntent).filter(ExecutionIntent.status == "CLOSED").count()
closed_outcomes = db.query(SignalOutcome).filter(SignalOutcome.exit_time.isnot(None)).count()

print(f"\nClosed ExecutionIntent: {closed_intents}")
print(f"Completed SignalOutcome: {closed_outcomes}")
print(f"Missing exit outcomes: {closed_intents - closed_outcomes}")

if closed_intents > closed_outcomes:
    print(f"\n❌ PROBLEM CONFIRMED:")
    print(f"   {closed_intents - closed_outcomes} trades were closed but exit outcomes NOT recorded!")
    print(f"\n   Solutions:")
    print(f"   1. Check exit.py, auto_exit.py, expiry_exit.py for error handling")
    print(f"   2. Add logging to record_exit_outcome() calls")
    print(f"   3. Ensure db.commit() is called after record_exit_outcome()")

db.close()
