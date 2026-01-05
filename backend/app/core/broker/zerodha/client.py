import os
from kiteconnect import KiteConnect

_kite = None

def get_kite_client() -> KiteConnect:
    global _kite

    if _kite:
        return _kite

    api_key = os.getenv("ZERODHA_API_KEY")
    access_token = os.getenv("ZERODHA_ACCESS_TOKEN")

    if not api_key or not access_token:
        raise RuntimeError("Zerodha API key or access token missing")

    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)

    _kite = kite
    return kite
