"""
REAL Options Chain Data from Zerodha
Fetches actual option premiums, OI, volume, and IV from Kite Connect API
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
import math
import pandas as pd

from app.services.zerodha import KiteConnectService
from app.core.broker.zerodha.instruments import load_instruments
from app.core.broker.zerodha_symbols import build_zerodha_option_symbol

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/options/real", tags=["options_real"])


def _bs_price(spot: float, strike: float, t: float, vol: float, r: float, opt_type: str) -> float:
    """Black-Scholes option price."""
    if t <= 0 or vol <= 0:
        return max(spot - strike, 0) if opt_type == "CE" else max(strike - spot, 0)
    sqrt_t = math.sqrt(t)
    d1 = (math.log(spot / strike) + (r + 0.5 * vol ** 2) * t) / (vol * sqrt_t)
    d2 = d1 - vol * sqrt_t
    N = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
    if opt_type == "CE":
        return spot * N(d1) - strike * math.exp(-r * t) * N(d2)
    return strike * math.exp(-r * t) * N(-d2) - spot * N(-d1)


def _calc_iv(ltp: float, spot: float, strike: float, t: float, r: float, opt_type: str) -> float:
    """Newton-Raphson IV solver. Returns IV as percentage (e.g. 18.5)."""
    if ltp <= 0 or t <= 0:
        return 0.0
    intrinsic = max(spot - strike, 0) if opt_type == "CE" else max(strike - spot, 0)
    if ltp <= intrinsic:
        return 0.0
    vol = 0.3  # initial guess
    sqrt_t = math.sqrt(t)
    N_pdf = lambda x: math.exp(-0.5 * x ** 2) / math.sqrt(2 * math.pi)
    for _ in range(50):
        price = _bs_price(spot, strike, t, vol, r, opt_type)
        d1 = (math.log(spot / strike) + (r + 0.5 * vol ** 2) * t) / (vol * sqrt_t)
        vega = spot * N_pdf(d1) * sqrt_t
        diff = price - ltp
        if abs(diff) < 0.001:
            break
        if vega < 1e-10:
            break
        vol -= diff / vega
        vol = max(0.001, min(vol, 5.0))
    return round(vol * 100, 2)


def _calc_greeks(spot: float, strike: float, t: float, vol_pct: float, r: float, opt_type: str) -> dict:
    """Black-Scholes Greeks. vol_pct is IV as percentage."""
    try:
        vol = vol_pct / 100.0
        if t <= 0 or vol <= 0:
            return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
        sqrt_t = math.sqrt(t)
        d1 = (math.log(spot / strike) + (r + 0.5 * vol ** 2) * t) / (vol * sqrt_t)
        d2 = d1 - vol * sqrt_t
        N = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
        N_pdf = lambda x: math.exp(-0.5 * x ** 2) / math.sqrt(2 * math.pi)
        gamma = round(N_pdf(d1) / (spot * vol * sqrt_t), 6)
        vega = round(spot * N_pdf(d1) * sqrt_t / 100, 4)
        if opt_type == "CE":
            delta = round(N(d1), 4)
            theta = round((-spot * N_pdf(d1) * vol / (2 * sqrt_t) - r * strike * math.exp(-r * t) * N(d2)) / 365, 4)
            rho = round(strike * t * math.exp(-r * t) * N(d2) / 100, 4)
        else:
            delta = round(-N(-d1), 4)
            theta = round((-spot * N_pdf(d1) * vol / (2 * sqrt_t) + r * strike * math.exp(-r * t) * N(-d2)) / 365, 4)
            rho = round(-strike * t * math.exp(-r * t) * N(-d2) / 100, 4)
        return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega, "rho": rho}
    except Exception:
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}

kite_service = KiteConnectService()

_CHAIN_CACHE: Dict[str, Dict[str, Any]] = {}
_EXPIRY_CACHE: Dict[str, Dict[str, Any]] = {}
_INSTRUMENTS_CACHE: Dict[str, Dict[str, Any]] = {}


def _cache_get(cache: Dict[str, Dict[str, Any]], key: str, ttl_seconds: int) -> Optional[Any]:
    payload = cache.get(key)
    if not payload:
        return None
    age = (datetime.now() - payload["ts"]).total_seconds()
    if age > ttl_seconds:
        cache.pop(key, None)
        return None
    return payload.get("value")


def _cache_set(cache: Dict[str, Dict[str, Any]], key: str, value: Any) -> None:
    cache[key] = {"ts": datetime.now(), "value": value}


def _get_instruments_cached(exchange: str = "NFO", ttl_seconds: int = 300) -> pd.DataFrame:
    key = f"instruments:{exchange}"
    cached = _cache_get(_INSTRUMENTS_CACHE, key, ttl_seconds)
    if cached is not None:
        return cached
    df = load_instruments(exchange=exchange)
    _cache_set(_INSTRUMENTS_CACHE, key, df)
    return df


@router.get("/chain/{symbol}")
async def get_real_option_chain(
    symbol: str,
    expiry: Optional[str] = None
):
    """
    Fetch REAL option chain data from Zerodha
    
    This replaces the simulated data with actual market data:
    - Real option premiums (LTP)
    - Real volume and OI
    - Real implied volatility
    - Real bid/ask prices
    - Actual Greeks calculated from market prices
    
    Args:
        symbol: NIFTY, BANKNIFTY, FINNIFTY
        expiry: Date in YYYY-MM-DD format
    
    Returns:
        Full option chain with real market data
    """
    try:
        symbol = symbol.upper().strip()
        
        # 1. Get real spot price
        logger.info(f"Fetching spot price for {symbol}")
        spot_data = kite_service.get_full_quote(symbol)
        if not spot_data or "last_price" not in spot_data:
            logger.error(f"Could not fetch spot price for {symbol} - API returned empty or invalid data")
            raise HTTPException(
                status_code=503,
                detail=f"Zerodha API is not responding for {symbol}. Please try again in a few moments."
            )
        
        spot = float(spot_data["last_price"])
        logger.info(f"✅ Got spot price for {symbol}: {spot}")
        
        # 2. Parse expiry date
        if not expiry:
            # Default to next Tuesday (NIFTY options expire on Tuesdays)
            today = datetime.now().date()
            days_until_tuesday = (1 - today.weekday()) % 7
            if days_until_tuesday == 0:
                days_until_tuesday = 7  # If today is Tuesday, get next Tuesday
            expiry_date = today + timedelta(days=days_until_tuesday)
        else:
            expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()

        cache_key = f"{symbol}:{expiry_date.isoformat()}"
        cached_chain = _cache_get(_CHAIN_CACHE, cache_key, ttl_seconds=8)
        if cached_chain is not None:
            return cached_chain
        
        # 3. Load instruments to get option tokens
        instruments = _get_instruments_cached(exchange="NFO")
        
        # Filter for this underlying and expiry
        symbol_options = instruments[
            (instruments['name'] == symbol) &
            (instruments['expiry'] == expiry_date) &
            (instruments['instrument_type'].isin(['CE', 'PE']))
        ]
        
        if symbol_options.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No options found for {symbol} expiry {expiry_date}"
            )
        
        # 4. Determine strike range (ATM ± 10 strikes)
        strike_step = 50 if symbol == "NIFTY" else 100
        atm_strike = round(spot / strike_step) * strike_step
        strikes_to_fetch = []
        for i in range(-10, 11):
            strikes_to_fetch.append(atm_strike + (i * strike_step))
        
        # 5. Build list of tradingsymbols to quote
        symbols_to_quote = []
        strike_map = {}  # Map tradingsymbol -> (strike, option_type)
        
        available_pairs = {
            (int(row["strike"]), str(row["instrument_type"]))
            for _, row in symbol_options[["strike", "instrument_type"]].iterrows()
            if row.get("strike") is not None
        }

        for strike in strikes_to_fetch:
            for opt_type in ['CE', 'PE']:
                if (int(strike), opt_type) in available_pairs:
                    tradingsymbol = build_zerodha_option_symbol(
                        underlying=symbol,
                        expiry=expiry_date,
                        strike=strike,
                        option_type=opt_type
                    )
                    symbols_to_quote.append(tradingsymbol)
                    strike_map[tradingsymbol] = (strike, opt_type)
        
        # 6. Fetch real quotes from Zerodha (batch)
        if not symbols_to_quote:
            raise HTTPException(
                status_code=404,
                detail=f"No valid option symbols found for strikes around {atm_strike}"
            )
        
        logger.info(f"Fetching {len(symbols_to_quote)} real option quotes from Zerodha")
        
        # Use Kite's bulk quote API - accepts list of "NFO:SYMBOL" format
        nfo_symbols = [f"NFO:{ts}" for ts in symbols_to_quote]
        
        try:
            logger.debug(f"Requesting quotes for symbols: {nfo_symbols[:3]}... ({len(nfo_symbols)} total)")
            quotes_response = kite_service.get_bulk_quotes(nfo_symbols)
            
            if not quotes_response:
                logger.error(
                    f"Failed to fetch quotes from Zerodha API for {len(nfo_symbols)} symbols. "
                    f"The API is either down or not responding. Please try again in a few moments."
                )
                raise HTTPException(
                    status_code=503,
                    detail="Zerodha API is temporarily unavailable. Please try again in a few moments."
                )
            
            logger.info(f"Successfully fetched {len(quotes_response)} option quotes from Zerodha")
            
            # Convert back to dict with tradingsymbol as key
            quotes = {}
            for nfo_symbol, quote_data in quotes_response.items():
                # Strip "NFO:" prefix to get tradingsymbol
                tradingsymbol = nfo_symbol.replace("NFO:", "")
                quotes[tradingsymbol] = quote_data
            
            if not quotes:
                logger.error("Quotes response was received but contained no data")
                raise HTTPException(
                    status_code=502,
                    detail="Zerodha API returned empty response. This may indicate a temporary issue."
                )
                
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error while fetching quotes from Zerodha: {type(e).__name__}: {e}. "
                f"Symbols requested: {len(nfo_symbols)}"
            )
            raise HTTPException(
                status_code=502,
                detail="Unexpected error while fetching market data. Please try again later."
            )
        
        # 7. Build option chain from real data
        today = datetime.now().date()
        days_to_expiry = (expiry_date - today).days
        chain_data = {}
        
        for tradingsymbol, quote_data in quotes.items():
            if tradingsymbol not in strike_map:
                continue
            
            strike, opt_type = strike_map[tradingsymbol]
            
            if strike not in chain_data:
                chain_data[strike] = {"strike": strike, "call": None, "put": None}
            
            # Extract real market data
            ltp = float(quote_data.get("last_price", 0))
            ohlc = quote_data.get("ohlc") or {}
            close = float(ohlc.get("close", 0))
            change = ltp - close
            change_percent = round((change / close * 100), 2) if close > 0 else 0.0

            # Greeks & IV from real LTP
            t = max(days_to_expiry / 365, 0.001)
            r = 0.07
            iv = _calc_iv(ltp, spot, strike, t, r, opt_type)
            greeks = _calc_greeks(spot, strike, t, iv, r, opt_type)

            option_data = {
                "ltp": ltp,
                "change": round(change, 2),
                "change_percent": change_percent,
                "volume": int(quote_data.get("volume", 0)),
                "oi": int(quote_data.get("oi", 0)),
                "iv": iv,
                "delta": greeks["delta"],
                "gamma": greeks["gamma"],
                "theta": greeks["theta"],
                "vega": greeks["vega"],
                "rho": greeks["rho"],
                "bid": float((quote_data.get("depth") or {}).get("buy", [{}])[0].get("price", 0) if quote_data.get("depth") else 0),
                "ask": float((quote_data.get("depth") or {}).get("sell", [{}])[0].get("price", 0) if quote_data.get("depth") else 0),
                "high": float(ohlc.get("high", 0)),
                "low": float(ohlc.get("low", 0)),
                "open": float(ohlc.get("open", 0)),
                "close": close,
            }

            # Calculate intrinsic value
            if opt_type == "CE":
                option_data["intrinsic"] = max(spot - strike, 0)
                chain_data[strike]["call"] = option_data
            else:
                option_data["intrinsic"] = max(strike - spot, 0)
                chain_data[strike]["put"] = option_data

            option_data["time_value"] = max(ltp - option_data["intrinsic"], 0)
        
        # 8. Sort strikes and convert to list
        sorted_strikes = sorted(chain_data.keys())
        strikes_list = [chain_data[s] for s in sorted_strikes]
        
        response_payload = {
            "symbol": symbol,
            "spot": round(spot, 2),
            "expiry": expiry_date.strftime("%Y-%m-%d"),
            "days_to_expiry": days_to_expiry,
            "strikes": strikes_list,
            "atm_strike": atm_strike,
            "total_strikes": len(strikes_list),
            "data_source": "ZERODHA_REAL",
            "timestamp": datetime.now().isoformat()
        }
        _cache_set(_CHAIN_CACHE, cache_key, response_payload)
        return response_payload
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Real options chain error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch real options chain: {str(e)}"
        )


@router.get("/expiries/{symbol}")
async def get_real_expiries(symbol: str):
    """Get actual expiry dates from Zerodha instruments"""
    try:
        symbol = symbol.upper()

        cached_expiries = _cache_get(_EXPIRY_CACHE, symbol, ttl_seconds=120)
        if cached_expiries is not None:
            return cached_expiries
        
        # Load instruments
        instruments = _get_instruments_cached(exchange="NFO")
        
        # Get unique expiries for this symbol
        symbol_options = instruments[
            (instruments['name'] == symbol) &
            (instruments['instrument_type'].isin(['CE', 'PE']))
        ]
        
        if symbol_options.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No options found for {symbol}"
            )
        
        # Extract and sort expiries
        expiries = sorted(symbol_options['expiry'].unique())
        expiry_strings = [exp.strftime("%Y-%m-%d") for exp in expiries]
        
        response_payload = {
            "symbol": symbol,
            "expiries": expiry_strings,
            "count": len(expiry_strings),
            "data_source": "ZERODHA_REAL"
        }
        _cache_set(_EXPIRY_CACHE, symbol, response_payload)
        return response_payload
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching real expiries: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
