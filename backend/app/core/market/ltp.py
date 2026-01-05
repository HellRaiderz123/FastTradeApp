from typing import List, Dict
from app.core.broker.zerodha.client import get_kite_client

def get_ltp(symbols: List[str]) -> Dict[str, float]:
    kite = get_kite_client()

    data = kite.ltp(symbols)
    return {
        sym: info["last_price"]
        for sym, info in data.items() # type: ignore
    }
