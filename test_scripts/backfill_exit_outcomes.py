#!/usr/bin/env python3
"""Backfill exit outcomes for closed trades that don't have signal outcomes"""
import sys
sys.path.insert(0, 'backend')

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent
from app.db.models_signal_outcome import SignalOutcome
from app.core.learning.signal_diagnostics import record_exit_outcome
from app.core.utils.time import now_ist

db = SessionLocal()

print("\n" + "="*80)
print("BACKFILL: Record Exit Outcomes for Closed Trades")
print("="*80)

# Find closed trades without signal outcomes
closed_intents = db.query(ExecutionIntent).filter(
    ExecutionIntent.status == "CLOSED"
).all()

print(f"\n📊 Total closed trades: {len(closed_intents)}")

# Check which ones don't have signal outcomes
missing = []
for intent in closed_intents:
    signal_outcome = db.query(SignalOutcome).filter(
        SignalOutcome.intent_id == intent.intent_id
    ).first()
    
    if not signal_outcome:
        missing.append(intent)

print(f"❌ Without signal outcomes: {len(missing)}")

if missing:
    print("\n🔄 Creating SignalOutcome records for closed trades...")
    for i, intent in enumerate(missing, 1):
        try:
            # Check if outcome just needs exit data recorded
            outcome = db.query(SignalOutcome).filter(
                SignalOutcome.intent_id == intent.intent_id
            ).first()
            
            if not outcome:
                # Need to create signal outcome from scratch using intent data
                from app.core.learning.signal_diagnostics import _safe_str
                
                # Reconstruct minimal signal outcome (entry + exit)
                outcome = SignalOutcome(
                    intent_id=intent.intent_id,
                    run_id=intent.run_id or 0,
                    underlying=_safe_str(intent.underlying),
                    strategy=_safe_str(intent.strategy),
                    signal_strength="UNKNOWN",
                    signal_bias="UNKNOWN",
                    confidence=0.0,
                    market_mode="UNKNOWN",
                    iv_regime="UNKNOWN",
                    entry_credit=float(intent.entry_credit or 0) if intent.entry_credit is not None else None,
                    entry_time=intent.created_at or now_ist(),
                    signal_json={},
                    context_json={},
                )
                db.add(outcome)
            
            # Now record the exit
            intent_cp = intent  # Use the intent as-is
            pnl = float(intent.pnl or 0)
            entry_credit = float(outcome.entry_credit or 0)
            pnl_pct = (pnl / entry_credit) * 100 if entry_credit > 0 else None
            
            if pnl > 0:
                outcome_label = "WIN"
            elif pnl < 0:
                outcome_label = "LOSS"
            else:
                outcome_label = "BREAKEVEN"
            
            outcome.exit_time = intent.closed_at or now_ist()
            outcome.pnl = pnl
            outcome.pnl_pct = pnl_pct
            outcome.exit_reason = _safe_str(getattr(intent, "exit_reason", None))
            outcome.outcome = outcome_label
            outcome.updated_at = now_ist()
            
            db.add(outcome)
            db.commit()
            
            print(f"  ✅ [{i}] {intent.intent_id[:8]}... | {intent.underlying} | P&L: ₹{pnl}")
            
        except Exception as e:
            db.rollback()
            print(f"  ❌ [{i}] {intent.intent_id[:8]}... | Error: {e}")

print("\n" + "="*80)
print("VERIFICATION:")
print("="*80)

# Re-check
now_count = db.query(SignalOutcome).filter(SignalOutcome.exit_time.isnot(None)).count()
print(f"\n✅ Exit outcomes recorded: {now_count}")

if now_count > 0:
    print(f"   Diagnostics should now show data!")
else:
    print(f"   Still no data - check logs above for errors")

db.close()
