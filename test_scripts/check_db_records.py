#!/usr/bin/env python3
"""Check actual database records"""
import sys
sys.path.insert(0, 'backend')

from app.db.session import SessionLocal
from app.db.models_signal_outcome import SignalOutcome

db = SessionLocal()

print("\n" + "="*80)
print("DATABASE VERIFICATION")
print("="*80)

# Get all   records with exit_time
closed = db.query(SignalOutcome).filter(SignalOutcome.exit_time.isnot(None)).all()
print(f"\nRecords with exit_time: {len(closed)}")

if closed:
    print("\nFirst 3 records with exit_time:")
    for i, rec in enumerate(closed[:3], 1):
        print(f"\n  [{i}] {rec.intent_id[:20]}...")
        print(f"      Exit Time: {rec.exit_time}")
        print(f"      P&L: {rec.pnl}")
        print(f"      P&L %: {rec.pnl_pct}")
        print(f"      Outcome: {rec.outcome}")
        print(f"      Exit Reason: {rec.exit_reason}")
else:
    print("  No records found!")

# Check if the backfill actually committed
print("\n" + "="*80)
print("COUNT BY  EXIT REASON:")
print("="*80)

from sqlalchemy import func

count_by_reason = db.query(
    SignalOutcome.exit_reason,
    func.count(SignalOutcome.id)
).filter(SignalOutcome.exit_reason.isnot(None)).group_by(SignalOutcome.exit_reason).all()

if count_by_reason:
    for reason, count in count_by_reason:
        print(f"  {reason}: {count}")
else:
    print("   No exit reasons recorded")

db.close()
