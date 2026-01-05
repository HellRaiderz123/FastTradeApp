"""
market_data.py
---------------
All market-data access lives here.
This file MUST NOT contain strategy logic.
"""

from typing import List, Dict
import pandas as pd
import random
import time

from app.core.broker.zerodha.instruments import get_index_token, load_instruments
from app.core.broker.zerodha.client import get_kite_client
from app.core.market.expiry import get_next_weekly_expiry


# ============================
# SPOT PRICE
# ============================

def get_spot(underlying: str) -> float: # type: ignore
    """
    Fetch live spot price.
    Replace stub with Zerodha / NSE API later.
    """
    # ---- TEMP STUB ----
    kite = get_kite_client()
    token = get_index_token(underlying)

    data = kite.ltp([token])
    return data[token]["last_price"] # type: ignore

# ============================
# ATM STRIKE
# ============================

def pick_atm_strike(underlying: str, spot: float) -> int:
    step = 50 if underlying == "NIFTY" else 100
    return int(round(spot / step) * step)


# ============================
# OPTION CHAIN
# ============================

def get_option_chain(underlying: str) -> pd.DataFrame:
    """
    REAL option chain from Zerodha instruments.
    """
    expiry = get_next_weekly_expiry()
    instruments = load_instruments()

    df = instruments[
        (instruments["name"] == underlying)
        & (instruments["expiry"] == pd.Timestamp(expiry))
        & (instruments["segment"] == "NFO-OPT")
    ].copy()

    df.rename(
        columns={
            "strike": "strike",
            "instrument_type": "instrument_type",
            "tradingsymbol": "tradingsymbol",
            "lot_size": "lot_size",
        },
        inplace=True,
    )

    return df[["strike", "instrument_type", "tradingsymbol", "lot_size"]]


# ============================
# OPTION LTP
# ============================

def get_option_ltp(symbols: List[str]) -> Dict[str, float]:
    """
    Fetch REAL option LTP from Zerodha.
    """
    kite = get_kite_client()

    symbols = [f"NFO:{sym}" for sym in symbols]
    data = kite.ltp(symbols)

    return {
        sym.split(":")[1]: info["last_price"]
        for sym, info in data.items()
    }



# ============================
# OI ENRICHMENT
# ============================

def enrich_chain_with_live_oi(chain_df: pd.DataFrame, *_):
    chain_df["oi"] = None
    return chain_df

