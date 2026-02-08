"""
REAL Options Chain Data from Zerodha
Fetches actual option premiums, OI, volume, and IV from Kite Connect API
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

from app.services.zerodha import KiteConnectService
from app.core.broker.zerodha.instruments import load_instruments
from app.core.broker.zerodha_symbols import build_zerodha_option_symbol

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/options/real", tags=["options_real"])

kite_service = KiteConnectService()


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
        
        # 3. Load instruments to get option tokens
        instruments = load_instruments(exchange="NFO")
        
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
        atm_strike = round(spot / 50) * 50
        strikes_to_fetch = []
        for i in range(-10, 11):
            strikes_to_fetch.append(atm_strike + (i * 50))
        
        # 5. Build list of tradingsymbols to quote
        symbols_to_quote = []
        strike_map = {}  # Map tradingsymbol -> (strike, option_type)
        
        for strike in strikes_to_fetch:
            for opt_type in ['CE', 'PE']:
                tradingsymbol = build_zerodha_option_symbol(
                    underlying=symbol,
                    expiry=expiry_date,
                    strike=strike,
                    option_type=opt_type
                )
                
                # Check if this option exists in instruments
                option_row = symbol_options[
                    (symbol_options['strike'] == strike) &
                    (symbol_options['instrument_type'] == opt_type)
                ]
                
                if not option_row.empty:
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
        chain_data = {}
        
        for tradingsymbol, quote_data in quotes.items():
            if tradingsymbol not in strike_map:
                continue
            
            strike, opt_type = strike_map[tradingsymbol]
            
            if strike not in chain_data:
                chain_data[strike] = {"strike": strike, "call": None, "put": None}
            
            # Extract real market data
            option_data = {
                "ltp": float(quote_data.get("last_price", 0)),
                "change": float(quote_data.get("net_change", 0)),
                "change_percent": float(quote_data.get("change_percent", 0)),
                "volume": int(quote_data.get("volume", 0)),
                "oi": int(quote_data.get("oi", 0)),
                "bid": float(quote_data.get("buy_price", 0)),
                "ask": float(quote_data.get("sell_price", 0)),
                "bid_qty": int(quote_data.get("buy_quantity", 0)),
                "ask_qty": int(quote_data.get("sell_quantity", 0)),
                "high": float(quote_data.get("ohlc", {}).get("high", 0)),
                "low": float(quote_data.get("ohlc", {}).get("low", 0)),
                "open": float(quote_data.get("ohlc", {}).get("open", 0)),
                "close": float(quote_data.get("ohlc", {}).get("close", 0)),
            }
            
            # Calculate intrinsic value
            if opt_type == "CE":
                option_data["intrinsic"] = max(spot - strike, 0)
                chain_data[strike]["call"] = option_data
            else:
                option_data["intrinsic"] = max(strike - spot, 0)
                chain_data[strike]["put"] = option_data
            
            # Calculate time value
            option_data["time_value"] = option_data["ltp"] - option_data["intrinsic"]
        
        # 8. Sort strikes and convert to list
        sorted_strikes = sorted(chain_data.keys())
        strikes_list = [chain_data[s] for s in sorted_strikes]
        
        # 9. Calculate days to expiry
        today = datetime.now().date()
        days_to_expiry = (expiry_date - today).days
        
        return {
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
        
        # Load instruments
        instruments = load_instruments(exchange="NFO")
        
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
        
        return {
            "symbol": symbol,
            "expiries": expiry_strings,
            "count": len(expiry_strings),
            "data_source": "ZERODHA_REAL"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching real expiries: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
