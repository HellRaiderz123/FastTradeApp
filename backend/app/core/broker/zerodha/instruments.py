import pandas as pd
from functools import lru_cache
import logging
from app.core.broker.zerodha.client import get_kite_client

logger = logging.getLogger(__name__)

INDEX_TOKENS = {
    "NIFTY": 256265,
    "BANKNIFTY": 260105,
    "FINNIFTY": 257801,
    "NIFTYVIX": 264969,   # India VIX (Zerodha)
}



@lru_cache(maxsize=1)
def load_instruments() -> pd.DataFrame:
    """
    Load all NFO instruments from Zerodha.
    Falls back to empty dataframe if API unavailable.
    """
    try:
        kite = get_kite_client()
        instruments = kite.instruments("NFO")
        logger.info(f"✅ Loaded {len(instruments)} NFO instruments from Zerodha")
        return pd.DataFrame(instruments)
    except Exception as e:
        logger.warning(f"⚠️  Could not load instruments ({e}), using empty fallback")
        # Return empty dataframe - strike selection will still work with ATM
        # but option chain will be empty
        return pd.DataFrame(columns=[
            "instrument_token", "name", "strike", "instrument_type",
            "expiry", "segment", "tradingsymbol", "lot_size"
        ])

def get_index_token(index: str) -> int:
    return INDEX_TOKENS[index]
