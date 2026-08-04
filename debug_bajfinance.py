import sys
sys.path.insert(0, '/app')
from app.core.market.ltp import get_ltp
from app.services.zerodha_ticker import get_cached_ltp
from app.core.broker.zerodha.client import get_kite_client

print("Cache for BAJFINANCE:", get_cached_ltp("BAJFINANCE"))
print("get_ltp result:", get_ltp(["BAJFINANCE"]))

k = get_kite_client()
raw = k.ltp(["NSE:BAJFINANCE"])
print("Direct kite.ltp:", raw)
