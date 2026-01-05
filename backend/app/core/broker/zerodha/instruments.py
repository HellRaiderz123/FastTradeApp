import pandas as pd
from functools import lru_cache
from app.core.broker.zerodha.client import get_kite_client


INDEX_TOKENS = {
    "NIFTY": 256265,
    "BANKNIFTY": 260105,
    "FINNIFTY": 257801,
}


@lru_cache(maxsize=1)
def load_instruments() -> pd.DataFrame:
    kite = get_kite_client()
    instruments = kite.instruments("NFO")
    return pd.DataFrame(instruments)

def get_index_token(index: str) -> int:
    return INDEX_TOKENS[index]
