"""Market data endpoints for live prices and option chain data."""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
import logging

from app.services.zerodha import KiteConnectService
from app.core.broker.zerodha.instruments import load_instruments
from app.services.market_data import get_option_ltp

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market", tags=["market"])

kite_service = KiteConnectService()


def _find_option_tradingsymbol(*, underlying: str, expiry: str, strike: int, option_type: str) -> str | None:
    """Find NFO tradingsymbol for an option contract via instruments list."""
    try:
        df = load_instruments()
        if df.empty:
            return None

        # Normalize
        underlying = underlying.upper().strip()
        option_type = option_type.upper().strip()
        if option_type not in {"CE", "PE"}:
            return None

        expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()

        # Zerodha instruments expiry is typically datetime-like; normalize to date
        expiry_series = df["expiry"]
        expiry_dates = expiry_series
        try:
            expiry_dates = expiry_series.apply(lambda x: x.date() if hasattr(x, "date") else x)
        except Exception:
            pass

        subset = df[
            (df["name"].astype(str).str.upper() == underlying)
            & (expiry_dates == expiry_date)
            & (df["strike"].astype(float) == float(strike))
            & (df["instrument_type"].astype(str).str.upper() == option_type)
        ]

        if subset.empty:
            return None

        return str(subset.iloc[0]["tradingsymbol"])
    except Exception:
        return None


@router.get("/ltp/{symbol}")
async def get_ltp(symbol: str = "NIFTY"):
    """
    Get latest trading price (LTP) for a symbol
    
    Args:
        symbol: Instrument symbol (e.g., 'NIFTY', 'BANKNIFTY')
    
    Returns:
        {
            "symbol": "NIFTY",
            "ltp": 26150.0,
            "timestamp": "2024-01-09T15:30:00"
        }
    """
    try:
        # Get LTP from Zerodha
        data = kite_service.get_quote(symbol)
        
        if data and "last_price" in data and data["last_price"] is not None:
            return {
                "symbol": symbol,
                "ltp": data.get("last_price"),
                "iv": data.get("iv"),
                "timestamp": datetime.now().isoformat()
            }
        
        # Fallback to default spot price if API fails
        logger.warning(f"Live LTP unavailable for {symbol}, using fallback")
        fallback_spots = {
            "NIFTY": 26150,
            "BANKNIFTY": 48500,
            "FINNIFTY": 24000,
        }
        
        return {
            "symbol": symbol,
            "ltp": fallback_spots.get(symbol, 26150),
            "iv": 18.0,
            "timestamp": datetime.now().isoformat(),
            "fallback": True
        }
    
    except Exception as e:
        logger.error(f"Error fetching LTP for {symbol}: {str(e)}")
        # Return fallback on error
        return {
            "symbol": symbol,
            "ltp": 26150,
            "iv": 18.0,
            "timestamp": datetime.now().isoformat(),
            "fallback": True,
            "error": str(e)
        }


@router.get("/expiries/{symbol}")
async def get_available_expiries(symbol: str = "NIFTY"):
    """
    Get available expiry dates for an option symbol
    NSE typically has weekly expiries on Thursdays
    
    Args:
        symbol: Instrument symbol (e.g., 'NIFTY', 'BANKNIFTY')
    
    Returns:
        {
            "symbol": "NIFTY",
            "expiries": [
                "2026-01-09",
                "2026-01-16",
                "2026-01-23"
            ]
        }
    """
    try:
        today = datetime.now().date()
        expiries = []
        
        # Find next Tuesday (NSE weekly expiry day)
        # In NSE, options expire on every Tuesday
        def next_tuesday(date):
            """Find next Tuesday from given date"""
            # Tuesday = 1 in Python (Monday=0, Sunday=6)
            days_until_tuesday = (1 - date.weekday()) % 7
            if days_until_tuesday == 0:
                # If today IS Tuesday, next expiry is next Tuesday
                days_until_tuesday = 7
            return date + timedelta(days=days_until_tuesday)
        
        # Generate weekly expiries (Tuesdays for next 13 weeks)
        current_date = today
        for _ in range(13):
            current_date = next_tuesday(current_date)
            expiries.append(current_date.strftime("%Y-%m-%d"))
            # Move past this date to find next Tuesday
            current_date = current_date + timedelta(days=1)
        
        # Remove duplicates and sort
        expiries = sorted(list(set(expiries)))
        
        return {
            "symbol": symbol,
            "expiries": expiries[:5]  # Return top 5 expiries
        }
    
    except Exception as e:
        logger.error(f"Error fetching expiries for {symbol}: {str(e)}")
        # Return fallback expiries
        today = datetime.now().date()
        fallback = [
            (today + timedelta(days=2)).strftime("%Y-%m-%d"),
            (today + timedelta(days=9)).strftime("%Y-%m-%d"),
            (today + timedelta(days=16)).strftime("%Y-%m-%d"),
            (today + timedelta(days=23)).strftime("%Y-%m-%d"),
            (today + timedelta(days=30)).strftime("%Y-%m-%d"),
        ]
        return {
            "symbol": symbol,
            "expiries": fallback
        }


@router.get("/option-premium")
async def get_option_premium(
    symbol: str = "NIFTY",
    strike: int = 26000,
    option_type: str = "CE",
    expiry: str = None
):
    """
    Get option premium for a specific strike and expiry
    
    Args:
        symbol: Underlying symbol
        strike: Strike price
        option_type: "CE" or "PE"
        expiry: Expiry date (YYYY-MM-DD)
    
    Returns:
        {
            "symbol": "NIFTY",
            "strike": 26000,
            "option_type": "CE",
            "expiry": "2026-01-09",
            "premium": 150.5,
            "iv": 18.5,
            "bid": 149.5,
            "ask": 151.5
        }
    """
    try:
        if not expiry:
            expiry = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        underlying = symbol.upper().strip()
        opt_type = option_type.upper().strip()

        tradingsymbol = _find_option_tradingsymbol(
            underlying=underlying,
            expiry=expiry,
            strike=strike,
            option_type=opt_type,
        )

        premium = 0.0
        if tradingsymbol:
            ltp_map = get_option_ltp([tradingsymbol])
            premium = float(ltp_map.get(tradingsymbol, 0.0) or 0.0)

        # Include spot (best-effort)
        spot = None
        try:
            spot_data = kite_service.get_quote(underlying)
            if spot_data and spot_data.get("last_price"):
                spot = float(spot_data.get("last_price"))
        except Exception:
            spot = None

        if premium <= 0:
            # Fallback estimation so UI still works when Zerodha token missing
            if spot is None:
                spot = 26150.0
            intrinsic = max(spot - strike, 0) if opt_type == "CE" else max(strike - spot, 0)
            time_value = 50 if underlying == "NIFTY" else 25
            premium = float(intrinsic + time_value)

            return {
                "symbol": underlying,
                "strike": strike,
                "option_type": opt_type,
                "expiry": expiry,
                "premium": premium,
                "estimated": True,
                "spot": spot,
                "tradingsymbol": tradingsymbol,
            }

        return {
            "symbol": underlying,
            "strike": strike,
            "option_type": opt_type,
            "expiry": expiry,
            "premium": premium,
            "estimated": False,
            "spot": spot,
            "tradingsymbol": tradingsymbol,
        }
    
    except Exception as e:
        logger.error(f"Error fetching premium for {symbol} {strike}{option_type}: {str(e)}")
        # Return estimated premium even on error
        return {
            "symbol": symbol,
            "strike": strike,
            "option_type": option_type,
            "expiry": expiry or datetime.now().strftime("%Y-%m-%d"),
            "premium": 50,
            "iv": 18.0,
            "bid": 49,
            "ask": 51,
            "estimated": True,
            "error": str(e)
        }


@router.get("/option-chain/{symbol}")
async def get_option_chain(symbol: str = "NIFTY", expiry: str = None):
    """
    Get full option chain for a symbol and expiry
    
    Args:
        symbol: Underlying symbol
        expiry: Expiry date (YYYY-MM-DD)
    
    Returns:
        {
            "symbol": "NIFTY",
            "spot": 26150,
            "expiry": "2026-01-09",
            "options": [
                {
                    "strike": 25900,
                    "ce_premium": 280,
                    "pe_premium": 30,
                    "ce_iv": 18.5,
                    "pe_iv": 16.2
                },
                ...
            ]
        }
    """
    try:
        if not expiry:
            expiry = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Get spot price
        spot_data = kite_service.get_quote(symbol)
        spot = spot_data.get("last_price", 26150) if spot_data else 26150
        
        underlying = symbol.upper().strip()

        interval = 50 if underlying == "NIFTY" else 100
        atm = int(round(spot / interval) * interval)

        strikes = list(range(atm - 1000, atm + 1000 + interval, interval))

        # Resolve tradingsymbols for this expiry and strikes
        ce_symbols: dict[int, str] = {}
        pe_symbols: dict[int, str] = {}
        all_symbols: list[str] = []

        for st in strikes:
            ce = _find_option_tradingsymbol(underlying=underlying, expiry=expiry, strike=st, option_type="CE")
            pe = _find_option_tradingsymbol(underlying=underlying, expiry=expiry, strike=st, option_type="PE")
            if ce:
                ce_symbols[st] = ce
                all_symbols.append(ce)
            if pe:
                pe_symbols[st] = pe
                all_symbols.append(pe)

        ltp_map = get_option_ltp(all_symbols) if all_symbols else {}

        options = []
        for st in strikes:
            ce_ts = ce_symbols.get(st)
            pe_ts = pe_symbols.get(st)
            ce_premium = float(ltp_map.get(ce_ts, 0.0) or 0.0) if ce_ts else 0.0
            pe_premium = float(ltp_map.get(pe_ts, 0.0) or 0.0) if pe_ts else 0.0

            if ce_premium > 0 or pe_premium > 0:
                options.append({
                    "strike": st,
                    "ce_premium": ce_premium,
                    "pe_premium": pe_premium,
                    "ce_tradingsymbol": ce_ts,
                    "pe_tradingsymbol": pe_ts,
                })
        
        return {
            "symbol": underlying,
            "spot": spot,
            "expiry": expiry,
            "options": options,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error fetching option chain for {symbol}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch option chain: {str(e)}"
        )
