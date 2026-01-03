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


# ============================
# SPOT PRICE
# ============================

def get_spot(underlying: str) -> float:
    """
    Fetch live spot price.
    Replace stub with Zerodha / NSE API later.
    """
    # ---- TEMP STUB ----
    if underlying == "NIFTY":
        return 22500.0
    elif underlying == "BANKNIFTY":
        return 48500.0
    return 0.0


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
    Returns option chain as DataFrame.
    Columns expected by your logic:
    - strike
    - instrument_type (PE / CE)
    - tradingsymbol
    - lot_size
    """
    step = 50 if underlying == "NIFTY" else 100
    atm = pick_atm_strike(underlying, get_spot(underlying))

    rows = []
    for i in range(-10, 11):
        strike = atm + (i * step)
        rows.append({
            "strike": strike,
            "instrument_type": "PE",
            "tradingsymbol": f"{underlying}{strike}PE",
            "lot_size": 50 if underlying == "NIFTY" else 25,
        })
        rows.append({
            "strike": strike,
            "instrument_type": "CE",
            "tradingsymbol": f"{underlying}{strike}CE",
            "lot_size": 50 if underlying == "NIFTY" else 25,
        })

    return pd.DataFrame(rows)


# ============================
# OPTION LTP
# ============================

def get_option_ltp(symbols: List[str]) -> Dict[str, float]:
    """
    Fetch LTP for option symbols.
    """
    ltp_map = {}
    for sym in symbols:
        # ---- TEMP STUB ----
        ltp_map[sym] = round(random.uniform(10, 250), 2)
    return ltp_map


# ============================
# OI ENRICHMENT
# ============================

def enrich_chain_with_live_oi(
    chain_df: pd.DataFrame,
    atm: int,
    underlying: str
) -> pd.DataFrame:
    """
    Adds OI column to option chain.
    """
    df = chain_df.copy()
    df["oi"] = df["strike"].apply(
        lambda s: max(0, int(1_00_000 - abs(s - atm) * 50))
    )
    return df
