import sys
from app.core.broker.zerodha.client import get_kite_client
k = get_kite_client()
try:
    r = k.ltp(['NSE:BAJFINANCE'])
    print('NSE result:', r)
except Exception as e:
    print('NSE error:', type(e).__name__, e)
try:
    r2 = k.ltp(['BSE:BAJFINANCE'])
    print('BSE result:', r2)
except Exception as e:
    print('BSE error:', type(e).__name__, e)
try:
    r3 = k.ltp(['NSE:BAJAJ-FINANCE'])
    print('NSE BAJAJ-FINANCE result:', r3)
except Exception as e:
    print('NSE BAJAJ-FINANCE error:', type(e).__name__, e)
