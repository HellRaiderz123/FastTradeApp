"""
market_data.py
---------------
All market-data access lives here.
This file MUST NOT contain strategy logic.
"""

from typing import List, Dict
import pandas as pd
import logging

from app.core.market.expiry import get_next_valid_expiry, get_next_weekly_expiry
from app.core.market.provider import fetch_ltp, fetch_spot as _provider_fetch_spot, get_bulk_quotes
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models_candles import Candle15m

logger = logging.getLogger(__name__)

# ============================
# SPOT PRICE
# ============================

def get_spot(underlying: str) -> float:
    """
    Fetch live spot price via the configured broker.
    Falls back to latest candle close if API unavailable.
    """
    # 1. Try broker-agnostic provider
    spot = _provider_fetch_spot(underlying)
    if spot and spot > 0:
        logger.info("✅ Got live spot: %s = %s", underlying, spot)
        return spot

    # 2. Fallback: latest candle close
    logger.warning("⚠️ Live spot unavailable for %s, falling back to latest candle", underlying)
    db = SessionLocal()
    try:
        latest = (
            db.query(Candle15m)
            .filter(Candle15m.symbol == underlying.upper())
            .order_by(Candle15m.timestamp.desc())
            .first()
        )
        if latest:
            logger.info("✅ Using latest candle close as spot: %s = %s", underlying, latest.close)
            return latest.close
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
    # Options/F&O instrument loading is Zerodha-specific (NFO segment)
    from app.core.broker.zerodha.instruments import load_instruments
    instruments = load_instruments()

    if instruments.empty:
        logger.warning("⚠️ No instruments loaded")
        return pd.DataFrame(columns=["strike", "instrument_type", "tradingsymbol", "lot_size"])

    expiry = get_next_valid_expiry(instruments, underlying)
    if not expiry:
        logger.warning("⚠️ No valid expiry found for %s", underlying)
        return pd.DataFrame(columns=["strike", "instrument_type", "tradingsymbol", "lot_size"])

    df = instruments[
        (instruments["name"] == underlying)
        & (pd.to_datetime(instruments["expiry"]).dt.date == expiry)
        & (instruments["segment"].str.contains("OPT"))
    ].copy()

    if df.empty:
        logger.warning("⚠️ Option chain empty for %s expiry %s", underlying, expiry)
        return pd.DataFrame(columns=["strike", "instrument_type", "tradingsymbol", "lot_size"])

    df["strike"] = df["strike"].astype(float)
    return df[["strike", "instrument_type", "tradingsymbol", "lot_size"]]


# ============================
# OPTION LTP
# ============================

def get_option_ltp(symbols: List[str]) -> Dict[str, float]:
    """
    Fetch option LTP. Options are NFO-segment instruments — currently
    only Zerodha supports F&O LTP directly. Falls back to 0 if unavailable.
    """
    try:
        from app.core.broker.zerodha.client import get_kite_client
        kite = get_kite_client()
        symbols_nfo = [f"NFO:{sym}" for sym in symbols]
        data = kite.ltp(symbols_nfo)
        logger.info("✅ Got LTP for %d option symbols", len(data))
        return {
            sym.split(":")[1]: info["last_price"]
            for sym, info in data.items()
        }
    except Exception as e:
        logger.warning("⚠️ Could not fetch option LTP (%s), using 0 as fallback", e)
        return {sym: 0.0 for sym in symbols}


# ============================
# OI ENRICHMENT
# ============================

def enrich_chain_with_live_oi(chain_df: pd.DataFrame, *_) -> pd.DataFrame:
    """
    Enrich option chain with live quote fields via the configured broker.
    Populates LTP, OI, volume, and best bid/ask metadata when available.
    """
    if chain_df is None:
        return pd.DataFrame()

    for col, default in {
        "ltp": 0.0, "oi": 0.0, "volume": 0.0,
        "bid": 0.0, "ask": 0.0, "bid_qty": 0.0, "ask_qty": 0.0,
    }.items():
        if col not in chain_df.columns:
            chain_df[col] = default

    if chain_df.empty:
        return chain_df

    try:
        symbols = [str(sym).strip() for sym in chain_df["tradingsymbol"].tolist() if str(sym).strip()]
        nfo_symbols = [sym if sym.startswith("NFO:") else f"NFO:{sym}" for sym in symbols]
        quotes = get_bulk_quotes(nfo_symbols) or {}

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

        chain_df["ltp"]     = chain_df["tradingsymbol"].map(lambda ts: _quote_value(ts, "last_price", 0.0))
        chain_df["oi"]      = chain_df["tradingsymbol"].map(lambda ts: _quote_value(ts, "oi", 0.0))
        chain_df["volume"]  = chain_df["tradingsymbol"].map(lambda ts: _quote_value(ts, "volume", 0.0))
        chain_df["bid"]     = chain_df["tradingsymbol"].map(lambda ts: _quote_value(ts, "bid", 0.0))
        chain_df["ask"]     = chain_df["tradingsymbol"].map(lambda ts: _quote_value(ts, "ask", 0.0))
        chain_df["bid_qty"] = chain_df["tradingsymbol"].map(lambda ts: _quote_value(ts, "buy_quantity", 0.0))
        chain_df["ask_qty"] = chain_df["tradingsymbol"].map(lambda ts: _quote_value(ts, "sell_quantity", 0.0))

        logger.info("✅ Enriched option chain with %d live quotes", len(quotes))

    except Exception as e:
        logger.warning("⚠️ Could not enrich chain (%s), using defaults", e)

    return chain_df

