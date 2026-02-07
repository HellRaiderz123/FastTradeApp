"""
Options Chain Data API
Comprehensive options chain with Greeks, OI, volume, and IV data
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
import math

from app.services.zerodha import KiteConnectService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/options", tags=["options"])

kite_service = KiteConnectService()


def calculate_greeks(spot: float, strike: float, time_to_expiry: float, 
                     volatility: float, rate: float, option_type: str) -> Dict[str, float]:
    """
    Calculate Black-Scholes Greeks
    
    Args:
        spot: Current underlying price
        strike: Strike price
        time_to_expiry: Time to expiry in years
        volatility: Implied volatility (decimal, e.g., 0.20 for 20%)
        rate: Risk-free rate (decimal)
        option_type: "CE" or "PE"
    
    Returns:
        Dict with delta, gamma, theta, vega, rho
    """
    try:
        if time_to_expiry <= 0:
            time_to_expiry = 0.001  # Minimum time to avoid division by zero
        
        # Black-Scholes intermediate calculations
        sqrt_t = math.sqrt(time_to_expiry)
        d1 = (math.log(spot / strike) + (rate + 0.5 * volatility ** 2) * time_to_expiry) / (volatility * sqrt_t)
        d2 = d1 - volatility * sqrt_t
        
        # Standard normal PDF and CDF
        def norm_pdf(x):
            return math.exp(-0.5 * x ** 2) / math.sqrt(2 * math.pi)
        
        def norm_cdf(x):
            return 0.5 * (1 + math.erf(x / math.sqrt(2)))
        
        # Greeks calculations
        if option_type == "CE":
            delta = norm_cdf(d1)
            theta = (-spot * norm_pdf(d1) * volatility / (2 * sqrt_t) - 
                    rate * strike * math.exp(-rate * time_to_expiry) * norm_cdf(d2)) / 365
        else:  # PE
            delta = -norm_cdf(-d1)
            theta = (-spot * norm_pdf(d1) * volatility / (2 * sqrt_t) + 
                    rate * strike * math.exp(-rate * time_to_expiry) * norm_cdf(-d2)) / 365
        
        gamma = norm_pdf(d1) / (spot * volatility * sqrt_t)
        vega = spot * norm_pdf(d1) * sqrt_t / 100  # Per 1% change in IV
        rho = (strike * time_to_expiry * math.exp(-rate * time_to_expiry) * 
               (norm_cdf(d2) if option_type == "CE" else -norm_cdf(-d2))) / 100
        
        return {
            "delta": round(delta, 4),
            "gamma": round(gamma, 6),
            "theta": round(theta, 4),
            "vega": round(vega, 4),
            "rho": round(rho, 4)
        }
    
    except Exception as e:
        logger.warning(f"Greeks calculation error: {e}")
        return {
            "delta": 0.0,
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0,
            "rho": 0.0
        }


@router.get("/chain/{symbol}")
async def get_option_chain(
    symbol: str,
    expiry: Optional[str] = None
):
    """
    Get full options chain with Greeks for a symbol and expiry
    
    NOTE: Currently using simulated option chain data with calculated Greeks.
    Real-time option chain data requires Zerodha instruments API lookup
    which needs instrument tokens for each strike.
    
    Simulated data includes:
    - Black-Scholes Greeks (Delta, Gamma, Theta, Vega, Rho)
    - Implied Volatility based on moneyness
    - Realistic volume and OI patterns around ATM
    - Bid/Ask spread simulation
    
    Args:
        symbol: Underlying symbol (NIFTY, BANKNIFTY, etc.)
        expiry: Expiry date (YYYY-MM-DD), defaults to nearest weekly expiry
    
    Returns:
        {
            "symbol": "NIFTY",
            "spot": 26150.0,
            "expiry": "2026-02-12",
            "days_to_expiry": 5,
            "strikes": [
                {
                    "strike": 26000,
                    "call": {
                        "ltp": 150.5,
                        "change": 12.5,
                        "change_percent": 9.0,
                        "volume": 125000,
                        "oi": 2345000,
                        "iv": 18.5,
                        "delta": 0.55,
                        "gamma": 0.003,
                        "theta": -5.2,
                        "vega": 12.5,
                        "bid": 149.5,
                        "ask": 151.5
                    },
                    "put": { ... }
                },
                ...
            ]
        }
    """
    try:
        symbol = symbol.upper().strip()
        
        # Get spot price
        spot_data = kite_service.get_full_quote(symbol)
        if spot_data and "last_price" in spot_data:
            spot = float(spot_data["last_price"])
        else:
            # Fallback spot prices
            spot = {"NIFTY": 26150.0, "BANKNIFTY": 48500.0, "FINNIFTY": 24000.0}.get(symbol, 1000.0)
        
        # Determine expiry
        if not expiry:
            today = datetime.now().date()
            # Next Thursday (weekly expiry for NIFTY/BANKNIFTY)
            days_until_thursday = (3 - today.weekday()) % 7
            if days_until_thursday == 0:
                days_until_thursday = 7
            expiry_date = today + timedelta(days=days_until_thursday)
            expiry = expiry_date.strftime("%Y-%m-%d")
        else:
            expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
        
        # Calculate days to expiry
        today = datetime.now().date()
        days_to_expiry = (expiry_date - today).days
        time_to_expiry = max(days_to_expiry / 365, 0.001)  # In years
        
        # Generate strike range (ATM ± 10 strikes)
        atm_strike = round(spot / 50) * 50  # Round to nearest 50
        strikes = []
        
        for i in range(-10, 11):
            strike = atm_strike + (i * 50)
            strikes.append(strike)
        
        # Build option chain data
        chain_data = []
        risk_free_rate = 0.07  # 7% (typical Indian risk-free rate)
        
        for strike in strikes:
            strike_data = {
                "strike": strike,
                "call": None,
                "put": None
            }
            
            # Calculate call option data
            try:
                # Simplified IV calculation (in production, fetch from market)
                moneyness = strike / spot
                if moneyness < 0.95:  # ITM call
                    iv = 0.15
                elif moneyness > 1.05:  # OTM call
                    iv = 0.22
                else:  # ATM call
                    iv = 0.18
                
                # Calculate intrinsic and time value
                intrinsic_call = max(spot - strike, 0)
                time_value = iv * spot * math.sqrt(time_to_expiry) * 0.4
                call_premium = intrinsic_call + time_value
                
                # Greeks
                call_greeks = calculate_greeks(spot, strike, time_to_expiry, iv, risk_free_rate, "CE")
                
                # Simulate volume and OI (in production, fetch from market)
                distance_from_atm = abs(strike - atm_strike)
                volume_factor = max(1 - (distance_from_atm / 500), 0.1)
                call_volume = int(50000 * volume_factor)
                call_oi = int(500000 * volume_factor)
                
                strike_data["call"] = {
                    "ltp": round(call_premium, 2),
                    "change": round((hash(f"{symbol}{strike}C") % 20) - 10, 2),
                    "change_percent": round((hash(f"{symbol}{strike}C") % 40) - 20, 2),
                    "volume": call_volume,
                    "oi": call_oi,
                    "iv": round(iv * 100, 2),
                    "delta": call_greeks["delta"],
                    "gamma": call_greeks["gamma"],
                    "theta": call_greeks["theta"],
                    "vega": call_greeks["vega"],
                    "rho": call_greeks["rho"],
                    "bid": round(call_premium * 0.98, 2),
                    "ask": round(call_premium * 1.02, 2),
                    "intrinsic": round(intrinsic_call, 2),
                    "time_value": round(time_value, 2)
                }
            except Exception as e:
                logger.warning(f"Error calculating call for strike {strike}: {e}")
                strike_data["call"] = None
            
            # Calculate put option data
            try:
                # Simplified IV calculation
                moneyness = strike / spot
                if moneyness > 1.05:  # ITM put
                    iv = 0.15
                elif moneyness < 0.95:  # OTM put
                    iv = 0.22
                else:  # ATM put
                    iv = 0.18
                
                # Calculate intrinsic and time value
                intrinsic_put = max(strike - spot, 0)
                time_value = iv * spot * math.sqrt(time_to_expiry) * 0.4
                put_premium = intrinsic_put + time_value
                
                # Greeks
                put_greeks = calculate_greeks(spot, strike, time_to_expiry, iv, risk_free_rate, "PE")
                
                # Simulate volume and OI
                distance_from_atm = abs(strike - atm_strike)
                volume_factor = max(1 - (distance_from_atm / 500), 0.1)
                put_volume = int(45000 * volume_factor)
                put_oi = int(480000 * volume_factor)
                
                strike_data["put"] = {
                    "ltp": round(put_premium, 2),
                    "change": round((hash(f"{symbol}{strike}P") % 20) - 10, 2),
                    "change_percent": round((hash(f"{symbol}{strike}P") % 40) - 20, 2),
                    "volume": put_volume,
                    "oi": put_oi,
                    "iv": round(iv * 100, 2),
                    "delta": put_greeks["delta"],
                    "gamma": put_greeks["gamma"],
                    "theta": put_greeks["theta"],
                    "vega": put_greeks["vega"],
                    "rho": put_greeks["rho"],
                    "bid": round(put_premium * 0.98, 2),
                    "ask": round(put_premium * 1.02, 2),
                    "intrinsic": round(intrinsic_put, 2),
                    "time_value": round(time_value, 2)
                }
            except Exception as e:
                logger.warning(f"Error calculating put for strike {strike}: {e}")
                strike_data["put"] = None
            
            chain_data.append(strike_data)
        
        return {
            "symbol": symbol,
            "spot": round(spot, 2),
            "expiry": expiry,
            "days_to_expiry": days_to_expiry,
            "time_to_expiry": round(time_to_expiry, 4),
            "strikes": chain_data,
            "atm_strike": atm_strike,
            "total_strikes": len(chain_data),
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Options chain error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch options chain: {str(e)}")


@router.get("/expiries/{symbol}")
async def get_expiries(symbol: str):
    """Get available expiry dates for options"""
    try:
        symbol = symbol.upper()
        today = datetime.now().date()
        expiries = []
        
        # Generate next 8 weekly expiries (Thursdays for NSE)
        for i in range(8):
            days_until_thursday = (3 - today.weekday()) % 7
            if days_until_thursday == 0 and i == 0:
                days_until_thursday = 7
            
            expiry_date = today + timedelta(days=days_until_thursday + (i * 7))
            expiries.append(expiry_date.strftime("%Y-%m-%d"))
        
        return {
            "symbol": symbol,
            "expiries": expiries,
            "count": len(expiries)
        }
    except Exception as e:
        logger.error(f"Error fetching expiries: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
