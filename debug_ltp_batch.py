import sys
sys.path.insert(0, '/app')
from app.core.broker.zerodha.client import get_kite_client

k = get_kite_client()

# Simulate what get_ltp does for a batch of stock symbols
symbols = ["BAJFINANCE", "NESTLEIND", "TITAN"]
normalized = [f"NSE:{s}" for s in symbols]
print("Calling kite.ltp with:", normalized)
data = k.ltp(normalized)
print("Result:", data)

for original, full in zip(symbols, normalized):
    info = data.get(full) or data.get(original)
    print(f"  {original} -> {full} -> info={info}")
    if info and isinstance(info, dict) and "last_price" in info:
        price = float(info["last_price"])
        print(f"    price={price}, > 0: {price > 0}")
