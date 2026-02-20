"""Test live option chain with LTP enrichment"""
import sys
sys.path.insert(0, "/app")

from app.services.market_data import get_option_chain, enrich_chain_with_live_oi

print("=" * 70)
print("✅ TESTING LIVE OPTION CHAIN WITH LTP ENRICHMENT")
print("=" * 70)
print()

try:
    # Fetch option chain
    chain = get_option_chain("NIFTY")
    print(f"✅ Got {len(chain)} option strikes from Zerodha instruments")
    print()
    
    # Show sample
    print("Sample strikes before enrichment:")
    print(chain[["strike", "instrument_type", "tradingsymbol", "lot_size"]].head(10))
    print()
    
    # Enrich with live LTP
    chain_enriched = enrich_chain_with_live_oi(chain)
    print("✅ Chain enriched with live LTP")
    print()
    
    # Show enriched sample
    print("Sample strikes after enrichment:")
    cols_to_show = ["strike", "instrument_type", "tradingsymbol", "lot_size", "ltp"]
    print(chain_enriched[cols_to_show].head(10))
    print()
    
    # Check LTP values
    has_ltp = chain_enriched["ltp"].notna().sum()
    print(f"✅ {has_ltp}/{len(chain_enriched)} strikes have LTP data")
    print()
    
    if has_ltp > 0:
        print("Sample LTP values:")
        print(chain_enriched[chain_enriched["ltp"] > 0][["strike", "instrument_type", "ltp"]].head(5))
    else:
        print("⚠️  No LTP values (expected if Zerodha API unavailable)")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
