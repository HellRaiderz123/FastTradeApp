"""
market_data.py
---------------
All market-data access lives here.
This file MUST NOT contain strategy logic.
"""

import time as _time
from typing import List, Dict
import pandas as pd
import logging

from app.core.market.expiry import get_next_valid_expiry, get_next_weekly_expiry
from app.core.market.provider import fetch_ltp, fetch_spot as _provider_fetch_spot, get_bulk_quotes
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models_candles import Candle15m

logger = logging.getLogger(__name__)

# Short-lived spot price cache (5 second TTL) — prevents duplicate broker calls
# when suggestions runs multiple underlyings in parallel threads.
_spot_cache: Dict[str, tuple] = {}  # symbol -> (price, expires_at)
_SPOT_TTL = 5.0

# PCR fast cache (60 second TTL) — ATM-only OI fetch for signal enrichment
_pcr_cache: Dict[str, tuple] = {}  # symbol -> (result_dict, expires_at)
_PCR_TTL = 60.0


# ============================
# SPOT PRICE
# ============================

def get_spot(underlying: str) -> float:
    """
    Fetch live spot price via the configured broker.
    Falls back to latest candle close if API unavailable.
    Uses a 5-second in-process cache to avoid duplicate broker calls
    when multiple threads request the same underlying simultaneously.
    """
    sym = underlying.upper()
    cached = _spot_cache.get(sym)
    if cached and _time.monotonic() < cached[1]:
        return cached[0]

    # 1. Try broker-agnostic provider
    spot = _provider_fetch_spot(underlying)
    if spot and spot > 0:
        logger.info("✅ Got live spot: %s = %s", underlying, spot)
        _spot_cache[sym] = (spot, _time.monotonic() + _SPOT_TTL)
        return spot

    # 2. Fallback: latest candle close
    logger.warning("⚠️ Live spot unavailable for %s, falling back to latest candle", underlying)
    db = SessionLocal()
    try:
        latest = (
            db.query(Candle15m)
            .filter(Candle15m.symbol == sym)
            .order_by(Candle15m.timestamp.desc())
            .first()
        )
        if latest:
            logger.info("✅ Using latest candle close as spot: %s = %s", underlying, latest.close)
            _spot_cache[sym] = (latest.close, _time.monotonic() + _SPOT_TTL)
            return latest.close
        raise RuntimeError(f"No spot data available for {underlying}")
    finally:
        db.close()

# ============================
# ATM STRIKE
# ============================

def get_pcr_fast(underlying: str, spot: float = 0.0) -> Dict:
    """
    Fetch PCR using only ATM ± 5 strikes (20 symbols max) instead of the full chain.
    ~10x faster than enrich_chain_with_live_oi. Cached for 60 seconds.
    Returns {pcr, sentiment, support, resistance, call_oi, put_oi} or {} on failure.
    """
    sym = underlying.upper()
    cached = _pcr_cache.get(sym)
    if cached and _time.monotonic() < cached[1]:
        return cached[0]

    try:
        if spot <= 0:
            spot = get_spot(sym)
        if spot <= 0:
            return {}

        step = 50 if sym == "NIFTY" else 100
        atm = int(round(spot / step) * step)
        strikes = [atm + step * i for i in range(-5, 6)]  # ATM ± 5

        chain_df = get_option_chain(sym)
        if chain_df is None or chain_df.empty:
            return {}

        chain_df = chain_df[chain_df["strike"].isin(strikes)].copy()
        if chain_df.empty:
            return {}

        symbols = [str(s).strip() for s in chain_df["tradingsymbol"].tolist() if str(s).strip()]
        nfo_symbols = [s if s.startswith("NFO:") else f"NFO:{s}" for s in symbols]
        quotes = get_bulk_quotes(nfo_symbols) or {}
        if not quotes:
            return {}

        call_oi = 0.0
        put_oi = 0.0
        max_call_oi, max_put_oi = 0.0, 0.0
        support, resistance = None, None

        for _, row in chain_df.iterrows():
            ts = str(row["tradingsymbol"])
            raw = quotes.get(f"NFO:{ts}") or quotes.get(ts) or {}
            oi = float(raw.get("oi", 0) or 0)
            strike = float(row["strike"])
            opt_type = str(row["instrument_type"]).upper()
            if opt_type == "CE":
                call_oi += oi
                if oi > max_call_oi:
                    max_call_oi, resistance = oi, strike
            elif opt_type == "PE":
                put_oi += oi
                if oi > max_put_oi:
                    max_put_oi, support = oi, strike

        if call_oi <= 0:
            return {}

        pcr = round(put_oi / call_oi, 4)
        if pcr < 0.75:
            sentiment = "Bullish"
        elif pcr > 1.25:
            sentiment = "Bearish"
        else:
            sentiment = "Neutral"

        result = {
            "pcr": pcr,
            "sentiment": sentiment,
            "support": support,
            "resistance": resistance,
            "call_oi": call_oi,
            "put_oi": put_oi,
        }
        _pcr_cache[sym] = (result, _time.monotonic() + _PCR_TTL)
        logger.info("✅ PCR fast fetch %s: pcr=%.2f sentiment=%s", sym, pcr, sentiment)
        return result
    except Exception as e:
        logger.warning("⚠️ PCR fast fetch failed for %s: %s", underlying, e)
        return {}


def pick_atm_strike(underlying: str, spot: float) -> int:
    step = 50 if underlying == "NIFTY" else 100
    return int(round(spot / step) * step)


# ============================
# OPTION CHAIN
# ============================

def get_option_chain(underlying: str) -> pd.DataFrame:
    from app.core.broker.registry import get_data_broker
    broker = get_data_broker()

    if broker == "INDMONEY":
        return _get_option_chain_indstocks(underlying)

    # Zerodha path
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


def _get_option_chain_indstocks(underlying: str) -> pd.DataFrame:
    """
    Build option chain for INDMoney broker from the instruments cache.
    The cache stores F&O by lookup key: UNDERLYING|EXPIRY|STRIKE|OPTTYPE -> scrip_code
    We reconstruct a chain DataFrame from those keys for the nearest expiry.
    """
    from app.core.broker.indstocks.market_data import _instruments_cache
    from app.core.market.expiry import get_current_weekly_expiry
    from datetime import date

    cache = _instruments_cache()
    prefix = f"{underlying.upper()}|"

    # Collect all F&O entries for this underlying
    rows = []
    for key, scrip in cache.items():
        if not key.startswith(prefix):
            continue
        parts = key.split("|")
        if len(parts) != 4:
            continue
        _, expiry_str, strike_str, opt_type = parts
        if not expiry_str or expiry_str == "0" or opt_type == "XX":
            continue
        try:
            expiry_date = date.fromisoformat(expiry_str)
            strike = float(strike_str)
        except (ValueError, TypeError):
            continue
        rows.append({
            "strike": strike,
            "instrument_type": opt_type,
            "tradingsymbol": scrip,  # scrip-code e.g. NFO_51234
            "lot_size": _LOT_SIZE_MAP.get(underlying.upper(), 50),
            "expiry": expiry_date,
        })

    if not rows:
        logger.warning("⚠️ INDstocks option chain empty for %s — instruments cache may not be loaded", underlying)
        return pd.DataFrame(columns=["strike", "instrument_type", "tradingsymbol", "lot_size"])

    df = pd.DataFrame(rows)
    today = date.today()
    future_expiries = sorted(df[df["expiry"] >= today]["expiry"].unique())
    if not future_expiries:
        logger.warning("⚠️ No future expiries found for %s in INDstocks cache", underlying)
        return pd.DataFrame(columns=["strike", "instrument_type", "tradingsymbol", "lot_size"])

    nearest_expiry = future_expiries[0]
    df = df[df["expiry"] == nearest_expiry].copy()
    logger.info("✅ INDstocks option chain: %s expiry=%s rows=%d", underlying, nearest_expiry, len(df))
    return df[["strike", "instrument_type", "tradingsymbol", "lot_size"]]


_LOT_SIZE_MAP = {
    "NIFTY": 65,
    "BANKNIFTY": 30,
    "FINNIFTY": 60,
    "MIDCPNIFTY": 120,
}


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

