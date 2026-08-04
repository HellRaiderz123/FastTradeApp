import sys
sys.path.insert(0, '/app')

# Patch get_ltp to add tracing
from app.services.zerodha_ticker import get_cached_ltp, subscribe_symbols
from app.core.broker.zerodha.client import get_kite_client
from typing import List, Dict

symbols = ["BAJFINANCE", "NESTLEIND", "TITAN", "BAJAJFINSV", "BAJAJ-AUTO", "ETERNAL", "HCLTECH", "HEROMOTOCO", "ICICIBANK", "M&M"]

print("Step 1: subscribe_symbols")
try:
    subscribe_symbols(symbols)
    print("  OK")
except Exception as e:
    print("  ERROR:", e)

print("Step 2: cache check")
out = {}
missing = []
for sym in symbols:
    cached = None
    try:
        cached = get_cached_ltp(sym)
    except Exception:
        cached = None
    if cached is not None and float(cached) > 0.5:
        out[sym] = float(cached)
        print(f"  {sym}: from cache = {cached}")
    else:
        missing.append(sym)
        print(f"  {sym}: missing (cache={cached})")

print("Step 3: REST call for missing:", missing)
kite = get_kite_client()
normalized = []
original_to_normalized = {}
for sym in missing:
    if ":" in sym:
        n = sym
    else:
        is_option = any(sym.upper().endswith(s) for s in ("CE", "PE", "FUT"))
        n = f"NFO:{sym}" if is_option else f"NSE:{sym}"
    normalized.append(n)
    original_to_normalized[sym] = n

print("  Normalized:", normalized)
try:
    data = kite.ltp(normalized)
    print("  REST result:", data)
    for original, full in original_to_normalized.items():
        info = data.get(full) or data.get(original)
        if info and isinstance(info, dict) and "last_price" in info:
            price = float(info["last_price"])
            if price > 0:
                out[original] = price
                print(f"  {original} = {price}")
            else:
                print(f"  {original}: price={price} skipped")
        else:
            print(f"  {original}: no info in response")
except Exception as e:
    print("  REST ERROR:", type(e).__name__, e)

print("Final out:", out)
