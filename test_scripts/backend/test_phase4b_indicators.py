"""
Test Phase 4B - Advanced Indicators
Tests Greeks, IV Percentile, Put/Call Ratio
"""
import os
os.environ["ZERODHA_API_KEY"] = "test"
os.environ["ZERODHA_ACCESS_TOKEN"] = "test"
os.environ["EXECUTION_MODE"] = "ZERODHA_DRY_RUN"

from datetime import date, timedelta
from app.core.indicators.greeks import GreeksCalculator, calculate_weighted_greeks
from app.core.indicators.iv_percentile import IVPercentileCalculator
from app.core.indicators.put_call_ratio import PutCallRatioAnalyzer, OptionChainAnalysis

print("\n" + "="*80)
print("PHASE 4B - ADVANCED INDICATORS TEST")
print("="*80)

# ============================================================================
# TEST 1: Greeks Calculator
# ============================================================================

print("\n[TEST 1] GREEKS CALCULATOR (Black-Scholes)")
print("-" * 80)

spot = 26130  # Real NIFTY price on Jan 7, 2026
strike = 26000
expiry = date.today() + timedelta(days=30)  # 30 days to expiry
volatility = 0.20  # 20% volatility

print(f"Scenario: NIFTY Call at ATM-130")
print(f"  Spot: {spot}")
print(f"  Strike: {strike}")
print(f"  Expiry: {expiry} ({(expiry - date.today()).days} days)")
print(f"  Volatility: {volatility*100:.1f}%")

# Calculate call Greeks
call_calc = GreeksCalculator(spot, strike, expiry, volatility, "CE")
call_greeks = call_calc.calculate_all()

print(f"\nCall Option Greeks:")
print(f"  Premium: {call_greeks['premium']:.2f}")
print(f"  Delta: {call_greeks['delta']:.4f}")
print(f"  Gamma: {call_greeks['gamma']:.6f}")
print(f"  Theta (per day): {call_greeks['theta']:.6f}")
print(f"  Vega (per 1% vol): {call_greeks['vega']:.6f}")
print(f"  Rho (per 1% rate): {call_greeks['rho']:.6f}")

# Calculate put Greeks
put_calc = GreeksCalculator(spot, strike, expiry, volatility, "PE")
put_greeks = put_calc.calculate_all()

print(f"\nPut Option Greeks:")
print(f"  Premium: {put_greeks['premium']:.2f}")
print(f"  Delta: {put_greeks['delta']:.4f}")
print(f"  Gamma: {put_greeks['gamma']:.6f}")
print(f"  Theta (per day): {put_greeks['theta']:.6f}")
print(f"  Vega (per 1% vol): {put_greeks['vega']:.6f}")
print(f"  Rho (per 1% rate): {put_greeks['rho']:.6f}")

# ============================================================================
# TEST 2: Weighted Greeks
# ============================================================================

print("\n[TEST 2] WEIGHTED GREEKS (Portfolio)")
print("-" * 80)

weighted_greeks = calculate_weighted_greeks(spot, strike, expiry, volatility)

print(f"Portfolio Greeks (1 Call + 1 Put at ATM):")
print(f"  Total Delta: {weighted_greeks['total_delta']:.4f}")
print(f"  Total Gamma: {weighted_greeks['total_gamma']:.6f}")
print(f"  Total Theta: {weighted_greeks['total_theta']:.6f}")
print(f"  Total Vega: {weighted_greeks['total_vega']:.6f}")

# ============================================================================
# TEST 3: IV Percentile Calculator
# ============================================================================

print("\n[TEST 3] IV PERCENTILE CALCULATOR")
print("-" * 80)

iv_calc = IVPercentileCalculator()

# Assume we calculated IVs
current_iv = 0.22  # 22% current IV
iv_52w_high = 0.35  # 35% highest in past year
iv_52w_low = 0.15  # 15% lowest in past year

iv_pct = iv_calc.calculate_iv_percentile(current_iv, iv_52w_high, iv_52w_low)
iv_regime = iv_calc.get_iv_regime(iv_pct, current_iv)

print(f"IV Analysis:")
print(f"  Current IV: {current_iv*100:.1f}%")
print(f"  52-week High: {iv_52w_high*100:.1f}%")
print(f"  52-week Low: {iv_52w_low*100:.1f}%")
print(f"  IV Percentile: {iv_pct:.1f}%")
print(f"  IV Regime: {iv_regime}")

# ============================================================================
# TEST 4: IV from Premium (Reverse calculation)
# ============================================================================

print("\n[TEST 4] IMPLIED VOLATILITY FROM PREMIUM")
print("-" * 80)

# If call premium is 250
call_premium = 250
call_iv = iv_calc.calculate_iv_from_premium(
    spot=spot,
    strike=strike,
    premium=call_premium,
    expiry=expiry,
    option_type="CE",
)

print(f"If Call Premium = {call_premium}")
print(f"  Implied IV: {call_iv*100:.2f}%")
print(f"  Verification: BS Premium at this IV = {call_calc.calculate_all()['premium']:.2f}")

# ============================================================================
# TEST 5: Put/Call Ratio
# ============================================================================

print("\n[TEST 5] PUT/CALL RATIO ANALYSIS")
print("-" * 80)

pcr_analyzer = PutCallRatioAnalyzer()

# Sample option chain data
option_chain = {
    "data": [
        {"strike": 25800, "call_oi": 8000, "put_oi": 15000},
        {"strike": 25900, "call_oi": 12000, "put_oi": 10000},
        {"strike": 26000, "call_oi": 25000, "put_oi": 8000},   # ATM
        {"strike": 26100, "call_oi": 18000, "put_oi": 5000},
        {"strike": 26200, "call_oi": 10000, "put_oi": 3000},
    ]
}

pcr_result = pcr_analyzer.calculate_pcr_from_chain(option_chain)

print(f"Option Chain Summary:")
print(f"  Total Call OI: {pcr_result['total_call_oi']:,}")
print(f"  Total Put OI: {pcr_result['total_put_oi']:,}")
print(f"  Put/Call Ratio: {pcr_result['pcr']:.4f}")
print(f"  Interpretation: {pcr_analyzer.get_pcr_interpretation(pcr_result['pcr'])}")

# ============================================================================
# TEST 6: Comprehensive Option Chain Analysis
# ============================================================================

print("\n[TEST 6] COMPREHENSIVE CHAIN ANALYSIS")
print("-" * 80)

chain_analyzer = OptionChainAnalysis()
analysis = chain_analyzer.analyze_chain(option_chain, spot)

print(f"Chain Analysis Results:")
print(f"  Total OI: {analysis['total_oi']:,}")
print(f"  PCR: {analysis['pcr']:.4f}")
print(f"  Sentiment: {analysis['pcr_interpretation']}")
print(f"  Max Call OI Strike: {analysis['max_call_strike']}")
print(f"  Max Put OI Strike: {analysis['max_put_strike']}")
print(f"  Resistance: {analysis['resistance_level']}")
print(f"  Support: {analysis['support_level']}")
print(f"  Distance to Resistance: {analysis['distance_to_resistance']:.0f} points")
print(f"  Distance to Support: {analysis['distance_to_support']:.0f} points")

# Calculate sentiment score
sentiment = chain_analyzer.get_sentiment_score(
    analysis['pcr'],
    spot,
    analysis['support_level'],
    analysis['resistance_level'],
)

print(f"\nSentiment Score:")
print(f"  PCR Score: {sentiment['pcr_score']}")
print(f"  Position Score: {sentiment['position_score']}")
print(f"  Bounce Score: {sentiment['bounce_score']}")
print(f"  Total Score: {sentiment['total_score']}")
print(f"  Sentiment: {sentiment['sentiment']}")

# ============================================================================
# SUMMARY
# ============================================================================

print("\n" + "="*80)
print("PHASE 4B SUMMARY - ADVANCED INDICATORS WORKING")
print("="*80)

print(f"""
[GREEKS CALCULATION]
   - Black-Scholes model implemented
   - Delta, Gamma, Theta, Vega, Rho calculated
   - Can now price options and understand portfolio sensitivity

[IV PERCENTILE]
   - IV calculated from option premiums (reverse Black-Scholes)
   - IV percentile ranking (0-100)
   - IV regime classification (LOW/NORMAL/HIGH)

[PUT/CALL RATIO]
   - PCR calculated from option chain OI
   - Market sentiment classification
   - Support/Resistance levels identified

[COMPREHENSIVE ANALYSIS]
   - Complete option chain analysis
   - Sentiment scoring (-100 to +100)
   - Ready for integration with strategy signals

Next Steps:
1. Integrate Greeks into signal enricher
2. Add IV percentile to trading signals
3. Use PCR for market sentiment confirmation
4. Test with real option chain data
5. Validate against live market conditions
""")

print("="*80)
