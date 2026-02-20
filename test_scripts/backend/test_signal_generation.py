"""Test the improved signal calculation"""
import sys
sys.path.insert(0, "/app")

from app.core.signals.ta_engine import ta_signal_15m
from app.db.session import SessionLocal

db = SessionLocal()
sig = ta_signal_15m(db, "NIFTY")

print("=" * 70)
print("✅ SIGNAL GENERATION TEST (AFTER FIXES)")
print("=" * 70)
print()

print(f"Signal:     {sig['signal']}")
print(f"Confidence: {sig['confidence']}%")
print(f"Bias:       {sig['bias']}")
print(f"IV Regime:  {sig['iv_regime']}")
print()

print("Indicators:")
print(f"  ADX:     {sig['indicators']['adx']} (was 10.71, expected ~26.33)")
print(f"  RSI:     {sig['indicators']['rsi']} (was 51.93, expected ~57.96)")
print(f"  Trend:   {sig['trend_score']}")
print()

print("Quality Checks (8-point system):")
for check, value in sig['quality_checks'].items():
    status = "✅" if value else "❌"
    print(f"  {status} {check}")
print()

print(f"Quality Score: {sig['quality_score']}/8")
print(f"Trade Readiness: {sig['trade_readiness_score']}/100")
print()

print("=" * 70)
if sig['quality_score'] >= 4:
    print("✅ Quality gate PASSED (>= 4/8)")
else:
    print("❌ Quality gate FAILED (< 4/8)")

db.close()
