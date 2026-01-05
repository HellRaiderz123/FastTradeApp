from app.core.broker.zerodha.client import get_kite_client
from app.core.broker.zerodha.instruments import get_index_token

def get_spot(underlying: str) -> float:
    kite = get_kite_client()
    token = get_index_token(underlying)

    data = kite.ltp([token])
    return data[token]["last_price"] # type: ignore
