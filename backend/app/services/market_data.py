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
import logging

from app.core.broker.zerodha.instruments import get_index_token, load_instruments
from app.core.broker.zerodha.client import get_kite_client
from app.core.market.expiry import get_next_valid_expiry, get_next_weekly_expiry
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models_candles import Candle15m

logger = logging.getLogger(__name__)

# ============================
# SPOT PRICE
# ============================

def get_spot(underlying: str) -> float: # type: ignore
    """
    Fetch live spot price from Zerodha.
    Falls back to latest candle close if API unavailable.
    """
    try:
        kite = get_kite_client()
        token = get_index_token(underlying)
        
        # Zerodha LTP returns data with integer token as key
        data = kite.ltp([token])
        
        # Check if token is in response (as integer or string)
        if token not in data and str(token) not in data:
            raise KeyError(f"Token {token} not in price response: {list(data.keys())}")
        
        # Get the data for this token
        price_data = data.get(token) or data.get(str(token))
        if not price_data:
            raise ValueError(f"No price data for token {token}")
        
        spot = price_data.get("last_price")
        if spot is None or spot <= 0:
            raise ValueError(f"Invalid spot price: {spot}")
        
        logger.info(f"✅ Got live spot from Zerodha: {underlying} = {spot}")
        return spot
        
    except Exception as e:
        logger.warning(f"⚠️  Zerodha API failed ({e}), falling back to latest candle")
        # Fallback: use latest candle close price
        db = SessionLocal()
        try:
            latest = (
                db.query(Candle15m)
                .filter(Candle15m.symbol == underlying.upper())
                .order_by(Candle15m.timestamp.desc())
                .first()
            )
            
            if latest:
                logger.info(f"✅ Using latest candle close as spot: {underlying} = {latest.close}")
                return latest.close
            else:
                logger.error(f"❌ No candle data found for {underlying}")
                raise RuntimeError(f"No spot data available for {underlying}")
        finally:
            db.close()

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
    instruments = load_instruments()

    if instruments.empty:
        logger.warning("⚠️ No instruments loaded")
        return pd.DataFrame(columns=["strike", "instrument_type", "tradingsymbol", "lot_size"])

    expiry = get_next_valid_expiry(instruments, underlying)
    if not expiry:
        logger.warning(f"⚠️ No valid expiry found for {underlying}")
        return pd.DataFrame(columns=["strike", "instrument_type", "tradingsymbol", "lot_size"])

    df = instruments[
        (instruments["name"] == underlying)
        & (pd.to_datetime(instruments["expiry"]).dt.date == expiry)
        & (instruments["segment"].str.contains("OPT"))
    ].copy()

    if df.empty:
        logger.warning(f"⚠️ Option chain empty for {underlying} expiry {expiry}")
        return pd.DataFrame(columns=["strike", "instrument_type", "tradingsymbol", "lot_size"])

    df["strike"] = df["strike"].astype(float)

    return df[["strike", "instrument_type", "tradingsymbol", "lot_size"]]



# ============================
# OPTION LTP
# ============================

def get_option_ltp(symbols: List[str]) -> Dict[str, float]:
    """
    Fetch REAL option LTP from Zerodha.
    Falls back to 0 if API unavailable.
    """
    try:
        kite = get_kite_client()
        symbols_nfo = [f"NFO:{sym}" for sym in symbols]
        data = kite.ltp(symbols_nfo)
        logger.info(f"✅ Got LTP for {len(data)} option symbols from Zerodha")
        return {
            sym.split(":")[1]: info["last_price"]
            for sym, info in data.items()
        }
    except Exception as e:
        logger.warning(f"⚠️  Could not fetch option LTP ({e}), using 0 as fallback")
        # Fallback: return 0 for all symbols
        return {sym: 0.0 for sym in symbols}



# ============================
# OI ENRICHMENT
# ============================

def enrich_chain_with_live_oi(chain_df: pd.DataFrame, *_) -> pd.DataFrame:
    """
    Enrich option chain with live LTP from Zerodha.
    """
    # Always add these columns
    if "ltp" not in chain_df.columns:
        chain_df["ltp"] = 0.0
    if "oi" not in chain_df.columns:
        chain_df["oi"] = None
    
    if chain_df.empty:
        return chain_df
    
    try:
        # Get LTP for all symbols
        symbols = chain_df["tradingsymbol"].tolist()
        ltp_data = get_option_ltp(symbols)
        
        # Update LTP column
        chain_df["ltp"] = chain_df["tradingsymbol"].map(ltp_data)
        logger.info(f"✅ Enriched option chain with {len(ltp_data)} LTP values")
        
    except Exception as e:
        logger.warning(f"⚠️  Could not enrich chain ({e}), using 0 for LTP")
        chain_df["ltp"] = 0.0
    
    return chain_df

