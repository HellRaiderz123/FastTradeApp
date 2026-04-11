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
from app.services.zerodha import KiteConnectService
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models_candles import Candle15m

logger = logging.getLogger(__name__)
_kite_service = KiteConnectService()

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
    Enrich option chain with live quote fields from Zerodha.

    Populates LTP, OI, volume, and best bid/ask metadata when available.
    Falls back gracefully if live data cannot be fetched.
    """
    if chain_df is None:
        return pd.DataFrame()

    # Always add these columns
    for col, default in {
        "ltp": 0.0,
        "oi": 0.0,
        "volume": 0.0,
        "bid": 0.0,
        "ask": 0.0,
        "bid_qty": 0.0,
        "ask_qty": 0.0,
    }.items():
        if col not in chain_df.columns:
            chain_df[col] = default

    if chain_df.empty:
        return chain_df

    try:
        symbols = [str(sym).strip() for sym in chain_df["tradingsymbol"].tolist() if str(sym).strip()]
        nfo_symbols = [sym if sym.startswith("NFO:") else f"NFO:{sym}" for sym in symbols]
        quotes = _kite_service.get_bulk_quotes(nfo_symbols) or {}

        if not quotes:
            logger.warning("⚠️ Could not fetch live option quotes; leaving chain enrichment at defaults")
            return chain_df

        def _quote_value(tradingsymbol: str, field: str, default=0.0):
            raw = quotes.get(f"NFO:{tradingsymbol}") or quotes.get(tradingsymbol) or {}
            if field == "bid":
                return float((raw.get("depth") or {}).get("buy", [{}])[0].get("price", default) or default)
            if field == "ask":
                return float((raw.get("depth") or {}).get("sell", [{}])[0].get("price", default) or default)
            return float(raw.get(field, default) or default)

        chain_df["ltp"] = chain_df["tradingsymbol"].map(lambda ts: _quote_value(ts, "last_price", 0.0))
        chain_df["oi"] = chain_df["tradingsymbol"].map(lambda ts: _quote_value(ts, "oi", 0.0))
        chain_df["volume"] = chain_df["tradingsymbol"].map(lambda ts: _quote_value(ts, "volume", 0.0))
        chain_df["bid"] = chain_df["tradingsymbol"].map(lambda ts: _quote_value(ts, "bid", 0.0))
        chain_df["ask"] = chain_df["tradingsymbol"].map(lambda ts: _quote_value(ts, "ask", 0.0))
        chain_df["bid_qty"] = chain_df["tradingsymbol"].map(lambda ts: _quote_value(ts, "buy_quantity", 0.0))
        chain_df["ask_qty"] = chain_df["tradingsymbol"].map(lambda ts: _quote_value(ts, "sell_quantity", 0.0))

        logger.info("✅ Enriched option chain with %d live quotes including OI/volume", len(quotes))

    except Exception as e:
        logger.warning(f"⚠️  Could not enrich chain ({e}), using 0/default values")

    return chain_df

