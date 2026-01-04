import os
from kiteconnect import KiteConnect


def get_kite_client() -> KiteConnect:
    api_key = os.getenv("ZERODHA_API_KEY")
    access_token = os.getenv("ZERODHA_ACCESS_TOKEN")

    if not api_key or not access_token:
        raise RuntimeError("Zerodha API key or access token missing")

    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    return kite
