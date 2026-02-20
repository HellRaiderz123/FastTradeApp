"""
Test script to verify real option chain data from Zerodha API
Run this to confirm the /options/real/chain endpoint works correctly
"""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
SYMBOL = "NIFTY"

def test_real_option_chain():
    """Test real option chain endpoint"""
    print("=" * 60)
    print("Testing REAL Option Chain Data from Zerodha")
    print("=" * 60)
    print()
    
    # Test 1: Get available expiries
    print("1. Fetching available expiries...")
    try:
        response = requests.get(f"{BASE_URL}/options/real/expiries/{SYMBOL}")
        response.raise_for_status()
        expiries_data = response.json()
        
        print(f"✅ Found {expiries_data['count']} expiries:")
        for exp in expiries_data['expiries'][:3]:
            print(f"   - {exp}")
        print()
        
        # Use first expiry for testing
        if not expiries_data['expiries']:
            print("❌ No expiries available")
            return
        
        test_expiry = expiries_data['expiries'][0]
        
    except Exception as e:
        print(f"❌ Failed to fetch expiries: {e}")
        return
    
    # Test 2: Get full option chain
    print(f"2. Fetching option chain for {SYMBOL} expiry {test_expiry}...")
    try:
        response = requests.get(
            f"{BASE_URL}/options/real/chain/{SYMBOL}",
            params={"expiry": test_expiry}
        )
        response.raise_for_status()
        chain_data = response.json()
        
        print(f"✅ Fetched option chain successfully!")
        print()
        print(f"📊 Chain Summary:")
        print(f"   Symbol: {chain_data['symbol']}")
        print(f"   Spot Price: ₹{chain_data['spot']:,.2f}")
        print(f"   Expiry: {chain_data['expiry']}")
        print(f"   Days to Expiry: {chain_data['days_to_expiry']}")
        print(f"   ATM Strike: {chain_data['atm_strike']}")
        print(f"   Total Strikes: {chain_data['total_strikes']}")
        print(f"   Data Source: {chain_data.get('data_source', 'UNKNOWN')}")
        print(f"   Timestamp: {chain_data['timestamp']}")
        print()
        
        # Verify data source
        if chain_data.get('data_source') == 'ZERODHA_REAL':
            print("✅ CONFIRMED: Using REAL Zerodha data!")
        else:
            print("⚠️  WARNING: Data source not marked as ZERODHA_REAL")
        print()
        
    except Exception as e:
        print(f"❌ Failed to fetch option chain: {e}")
        return
    
    # Test 3: Analyze ATM strike data
    print("3. Analyzing ATM strike data...")
    try:
        atm_strike = chain_data['atm_strike']
        atm_data = None
        
        for strike in chain_data['strikes']:
            if strike['strike'] == atm_strike:
                atm_data = strike
                break
        
        if atm_data:
            print(f"✅ ATM Strike {atm_strike} Data:")
            print()
            
            if atm_data.get('call'):
                call = atm_data['call']
                print(f"   📈 CALL Option:")
                print(f"      LTP: ₹{call.get('ltp', 0):,.2f}")
                print(f"      Volume: {call.get('volume', 0):,}")
                print(f"      OI: {call.get('oi', 0):,}")
                print(f"      Bid: ₹{call.get('bid', 0):,.2f}")
                print(f"      Ask: ₹{call.get('ask', 0):,.2f}")
                print(f"      Day High: ₹{call.get('high', 0):,.2f}")
                print(f"      Day Low: ₹{call.get('low', 0):,.2f}")
                print(f"      Change: ₹{call.get('change', 0):,.2f}")
                print()
            
            if atm_data.get('put'):
                put = atm_data['put']
                print(f"   📉 PUT Option:")
                print(f"      LTP: ₹{put.get('ltp', 0):,.2f}")
                print(f"      Volume: {put.get('volume', 0):,}")
                print(f"      OI: {put.get('oi', 0):,}")
                print(f"      Bid: ₹{put.get('bid', 0):,.2f}")
                print(f"      Ask: ₹{put.get('ask', 0):,.2f}")
                print(f"      Day High: ₹{put.get('high', 0):,.2f}")
                print(f"      Day Low: ₹{put.get('low', 0):,.2f}")
                print(f"      Change: ₹{put.get('change', 0):,.2f}")
                print()
        else:
            print(f"⚠️  ATM strike {atm_strike} not found in data")
        
    except Exception as e:
        print(f"❌ Failed to analyze ATM data: {e}")
    
    # Test 4: Check data quality
    print("4. Data Quality Checks:")
    print()
    
    checks_passed = 0
    total_checks = 0
    
    # Check 1: All strikes have data
    total_checks += 1
    if all(s.get('call') or s.get('put') for s in chain_data['strikes']):
        print("   ✅ All strikes have option data")
        checks_passed += 1
    else:
        print("   ❌ Some strikes missing option data")
    
    # Check 2: Volume is realistic (not all same)
    total_checks += 1
    volumes = [s['call']['volume'] for s in chain_data['strikes'] if s.get('call') and s['call'].get('volume')]
    if len(set(volumes)) > 1:
        print("   ✅ Volume varies across strikes (realistic)")
        checks_passed += 1
    else:
        print("   ❌ All volumes are same (likely simulated)")
    
    # Check 3: Bid < LTP < Ask
    total_checks += 1
    bid_ask_valid = True
    for strike in chain_data['strikes']:
        for opt in [strike.get('call'), strike.get('put')]:
            if opt:
                ltp = opt.get('ltp', 0)
                bid = opt.get('bid', 0)
                ask = opt.get('ask', 0)
                if bid > 0 and ask > 0:
                    if not (bid <= ltp <= ask):
                        bid_ask_valid = False
                        break
    
    if bid_ask_valid:
        print("   ✅ Bid/Ask spreads are valid")
        checks_passed += 1
    else:
        print("   ⚠️  Some Bid/Ask spreads look unusual")
    
    # Check 4: Has timestamp
    total_checks += 1
    if 'timestamp' in chain_data:
        print("   ✅ Data has timestamp")
        checks_passed += 1
    else:
        print("   ❌ Missing timestamp")
    
    print()
    print(f"Quality Score: {checks_passed}/{total_checks} checks passed")
    print()
    
    # Final summary
    print("=" * 60)
    if checks_passed == total_checks and chain_data.get('data_source') == 'ZERODHA_REAL':
        print("✅ SUCCESS: Option chain is using REAL Zerodha data!")
    elif chain_data.get('data_source') != 'ZERODHA_REAL':
        print("⚠️  WARNING: Still using simulated data")
        print("   Make sure to update frontend API endpoint to /options/real/...")
    else:
        print("⚠️  PARTIAL: Real data but quality checks failed")
    print("=" * 60)


def test_stub_vs_real():
    """Compare stub vs real data side by side"""
    print()
    print("=" * 60)
    print("Comparing STUB vs REAL Data")
    print("=" * 60)
    print()
    
    try:
        # Fetch stub data
        print("Fetching STUB data from /options/chain...")
        stub_response = requests.get(f"{BASE_URL}/options/chain/{SYMBOL}")
        stub_data = stub_response.json()
        
        # Fetch real data
        print("Fetching REAL data from /options/real/chain...")
        real_response = requests.get(f"{BASE_URL}/options/real/chain/{SYMBOL}")
        real_data = real_response.json()
        
        print()
        print(f"Comparison for ATM Strike:")
        print()
        
        stub_atm = next((s for s in stub_data['strikes'] if s['strike'] == stub_data['atm_strike']), None)
        real_atm = next((s for s in real_data['strikes'] if s['strike'] == real_data['atm_strike']), None)
        
        if stub_atm and real_atm:
            print(f"{'Metric':<20} {'STUB (Simulated)':<25} {'REAL (Zerodha)':<25}")
            print("-" * 70)
            
            # Compare call options
            if stub_atm.get('call') and real_atm.get('call'):
                stub_call = stub_atm['call']
                real_call = real_atm['call']
                
                print(f"{'Call LTP':<20} ₹{stub_call.get('ltp', 0):<24.2f} ₹{real_call.get('ltp', 0):<24.2f}")
                print(f"{'Call Volume':<20} {stub_call.get('volume', 0):<24,} {real_call.get('volume', 0):<24,}")
                print(f"{'Call OI':<20} {stub_call.get('oi', 0):<24,} {real_call.get('oi', 0):<24,}")
                print(f"{'Call Bid':<20} ₹{stub_call.get('bid', 0):<24.2f} ₹{real_call.get('bid', 0):<24.2f}")
                print(f"{'Call Ask':<20} ₹{stub_call.get('ask', 0):<24.2f} ₹{real_call.get('ask', 0):<24.2f}")
            
            print()
            print("💡 Notice the differences:")
            print("   - STUB data is calculated/simulated")
            print("   - REAL data comes from actual market quotes")
            
    except Exception as e:
        print(f"❌ Comparison failed: {e}")


if __name__ == "__main__":
    try:
        test_real_option_chain()
        
        # Uncomment to see side-by-side comparison
        # test_stub_vs_real()
        
    except KeyboardInterrupt:
        print("\n⚠️  Test cancelled by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
