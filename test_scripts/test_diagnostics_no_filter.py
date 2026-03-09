#!/usr/bin/env python3
"""Test signal diagnostics without lookback filter"""
import sys
sys.path.insert(0, 'backend')

from app.db.session import SessionLocal
from app.api.routes.journal import signal_diagnostics

db = SessionLocal()

print("\n" + "="*80)
print("TESTING SIGNAL DIAGNOSTICS - NO LOOKBACK FILTER")
print("="*80)

try:
    result = signal_diagnostics(
        limit=200,
        lookback_days=None,  # No time filter
        db=db
    )
    
    print(f"\n✅ API called successfully!")
    print(f"\n📊 Summary:")
    summary = result.get('summary', {})
    print(f"   Trades: {summary.get('trades', 0)}")
    print(f"   Wins: {summary.get('wins', 0)}")
    print(f"   Losses: {summary.get('losses', 0)}")
    print(f"   Win Rate: {summary.get('win_rate_pct', 0)}%")
    print(f"   Net P&L: ₹{summary.get('net_pnl', 0)}")
    print(f"   Profit Factor: {summary.get('profit_factor', 'N/A')}")
    
    print(f"\n📈 By Signal Bias:")
    for key, value in result.get('by_signal_bias', {}).items():
        print(f"   {key}: {value['trades']} trades, {value['win_rate_pct']}% win, ₹{value['net_pnl']} P&L")
    
    print(f"\n📊 By Strategy:")
    for key, value in result.get('by_strategy', {}).items():
        print(f"   {key}: {value['trades']} trades, {value['win_rate_pct']}% win, ₹{value['net_pnl']} P&L")
    
    print(f"\n🎯 Loss Drivers (Bias + Strategy):")
    for key, value in result.get('by_bias_strategy', {}).items():
        print(f"   {key}: {value['trades']} trades, {value['win_rate_pct']}% win, ₹{value['net_pnl']} P&L")
    
    if summary.get('trades', 0) > 0:
        print("\n✅ SUCCESS! Diagnostics data is populated!")
    else:
        print("\n⚠️ Still no data even without lookback filter")
        print("    This means the exit_time records might not be correct")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

db.close()
