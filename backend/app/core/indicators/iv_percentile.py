"""
IV Percentile Calculator
Calculate implied volatility from option premiums and compare to historical range
"""

import logging
import math
from typing import Dict, Optional, Tuple
from datetime import date
from scipy.optimize import brentq
from scipy.stats import norm

logger = logging.getLogger(__name__)


class IVPercentileCalculator:
    """Calculate IV percentile from option chain"""
    
    def __init__(self, db = None):
        """Initialize IV calculator"""
        self.db = db
    
    def calculate_iv_from_premium(
        self,
        spot: float,
        strike: float,
        premium: float,
        expiry: date,
        option_type: str = "CE",
        risk_free_rate: float = 0.065,
        dividend_yield: float = 0.015,
    ) -> Optional[float]:
        """
        Calculate implied volatility from option premium using Newton-Raphson
        
        Args:
            spot: Current spot price
            strike: Strike price
            premium: Option premium
            expiry: Expiry date
            option_type: "CE" or "PE"
            risk_free_rate: Risk-free rate
            dividend_yield: Dividend yield
        
        Returns:
            Implied volatility (0-1 scale)
        """
        try:
            from datetime import datetime
            today = date.today()
            days_to_expiry = (expiry - today).days
            tau = max(days_to_expiry / 365.0, 0.001)
            
            # Use Brent's method to find IV
            def bs_price(vol):
                d1 = (
                    math.log(spot / strike)
                    + (risk_free_rate - dividend_yield + 0.5 * vol ** 2) * tau
                ) / (vol * math.sqrt(tau))
                
                d2 = d1 - vol * math.sqrt(tau)
                
                if option_type.upper() == "CE":
                    price = (
                        spot * math.exp(-dividend_yield * tau) * norm.cdf(d1)
                        - strike * math.exp(-risk_free_rate * tau) * norm.cdf(d2)
                    )
                else:  # PE
                    price = (
                        strike * math.exp(-risk_free_rate * tau) * norm.cdf(-d2)
                        - spot * math.exp(-dividend_yield * tau) * norm.cdf(-d1)
                    )
                
                return price - premium
            
            # Search for IV between 0.01 and 2.0 (1% to 200%)
            try:
                iv = brentq(bs_price, 0.01, 2.0, maxiter=100)
                return round(iv, 4)
            except ValueError:
                # If brentq fails, return None
                return None
        
        except Exception as e:
            logger.warning(f"Error calculating IV: {e}")
            return None
    
    def calculate_atm_iv(
        self,
        spot: float,
        atm_strike: float,
        call_premium: float,
        put_premium: float,
        expiry: date,
    ) -> Optional[float]:
        """
        Calculate ATM implied volatility (average of call and put IV)
        """
        try:
            call_iv = self.calculate_iv_from_premium(
                spot, atm_strike, call_premium, expiry, "CE"
            )
            put_iv = self.calculate_iv_from_premium(
                spot, atm_strike, put_premium, expiry, "PE"
            )
            
            if call_iv and put_iv:
                atm_iv = (call_iv + put_iv) / 2
                return round(atm_iv, 4)
            elif call_iv:
                return call_iv
            elif put_iv:
                return put_iv
            else:
                return None
        
        except Exception as e:
            logger.warning(f"Error calculating ATM IV: {e}")
            return None
    
    def calculate_iv_percentile(
        self,
        current_iv: float,
        iv_52w_high: float,
        iv_52w_low: float,
    ) -> Optional[float]:
        """
        Calculate IV percentile
        IV Percentile = (Current IV - 52w Low) / (52w High - 52w Low) × 100
        
        Args:
            current_iv: Current implied volatility
            iv_52w_high: 52-week high IV
            iv_52w_low: 52-week low IV
        
        Returns:
            IV Percentile (0-100)
        """
        try:
            if iv_52w_high == iv_52w_low:
                return 50.0  # Neutral if no range
            
            iv_pct = ((current_iv - iv_52w_low) / (iv_52w_high - iv_52w_low)) * 100
            iv_pct = max(0, min(100, iv_pct))  # Clamp to 0-100
            
            return round(iv_pct, 2)
        
        except Exception as e:
            logger.warning(f"Error calculating IV percentile: {e}")
            return None
    
    def get_iv_regime(
        self,
        iv_percentile: Optional[float],
        current_iv: Optional[float] = None,
    ) -> str:
        """
        Determine IV regime based on IV percentile
        
        Returns: "LOW", "NORMAL", or "HIGH"
        """
        if iv_percentile is None:
            return "NORMAL"
        
        if iv_percentile >= 75:
            return "HIGH"
        elif iv_percentile >= 50:
            return "NORMAL"
        else:
            return "LOW"


class OptionChainIVAnalysis:
    """Analyze IV surface from option chain"""
    
    def __init__(self, option_chain: Dict):
        """
        Initialize with option chain data
        
        Args:
            option_chain: {
                "data": [
                    {"strike": 26000, "call_bid": 100, "call_ask": 105, "put_bid": 50, "put_ask": 55},
                    ...
                ]
            }
        """
        self.chain = option_chain
        self.iv_calc = IVPercentileCalculator()
    
    def calculate_iv_surface(
        self,
        spot: float,
        expiry: date,
    ) -> Dict[float, Dict[str, float]]:
        """
        Calculate IV for all strikes in the option chain
        
        Returns:
            {
                26000: {"call_iv": 0.25, "put_iv": 0.24, "mid_iv": 0.245},
                26100: {...},
                ...
            }
        """
        try:
            iv_surface = {}
            
            data = self.chain.get("data", [])
            
            for item in data:
                strike = item.get("strike")
                if not strike:
                    continue
                
                # Use mid prices
                call_mid = (item.get("call_bid", 0) + item.get("call_ask", 0)) / 2
                put_mid = (item.get("put_bid", 0) + item.get("put_ask", 0)) / 2
                
                if call_mid == 0 or put_mid == 0:
                    continue
                
                call_iv = self.iv_calc.calculate_iv_from_premium(
                    spot, strike, call_mid, expiry, "CE"
                )
                put_iv = self.iv_calc.calculate_iv_from_premium(
                    spot, strike, put_mid, expiry, "PE"
                )
                
                if call_iv or put_iv:
                    iv_surface[strike] = {
                        "call_iv": call_iv or 0.0,
                        "put_iv": put_iv or 0.0,
                        "mid_iv": (call_iv + put_iv) / 2 if (call_iv and put_iv) else (call_iv or put_iv or 0.0),
                    }
            
            return iv_surface
        
        except Exception as e:
            logger.error(f"Error calculating IV surface: {e}")
            return {}
    
    def get_atm_iv(
        self,
        spot: float,
        expiry: date,
    ) -> Optional[float]:
        """Get IV at ATM strike"""
        try:
            # Find ATM strike
            data = self.chain.get("data", [])
            atm_strike = None
            min_diff = float("inf")
            
            for item in data:
                strike = item.get("strike")
                if not strike:
                    continue
                
                diff = abs(strike - spot)
                if diff < min_diff:
                    min_diff = diff
                    atm_strike = strike
            
            if not atm_strike:
                return None
            
            # Find ATM data
            for item in data:
                if item.get("strike") == atm_strike:
                    call_mid = (item.get("call_bid", 0) + item.get("call_ask", 0)) / 2
                    put_mid = (item.get("put_bid", 0) + item.get("put_ask", 0)) / 2
                    
                    if call_mid and put_mid:
                        return self.iv_calc.calculate_atm_iv(
                            spot, atm_strike, call_mid, put_mid, expiry
                        )
            
            return None
        
        except Exception as e:
            logger.warning(f"Error getting ATM IV: {e}")
            return None
    
    def get_iv_skew(
        self,
        spot: float,
        expiry: date,
    ) -> Dict[str, float]:
        """
        Calculate IV skew (call IV vs put IV across strikes)
        
        Returns:
            {
                "skew_magnitude": 0.05,  # Difference between OTM put and call IV
                "skew_direction": "put",  # Which is higher
                "atm_iv": 0.25,
            }
        """
        try:
            iv_surface = self.calculate_iv_surface(spot, expiry)
            
            if not iv_surface:
                return {}
            
            # Find OTM strikes (1-2 strikes below/above ATM)
            strikes = sorted(iv_surface.keys())
            atm_idx = min(range(len(strikes)), key=lambda i: abs(strikes[i] - spot))
            
            atm_iv = iv_surface[strikes[atm_idx]].get("mid_iv", 0)
            
            # Get OTM put and call IVs
            otm_put_iv = None
            otm_call_iv = None
            
            if atm_idx > 0:
                otm_put_iv = iv_surface[strikes[atm_idx - 1]].get("put_iv")
            
            if atm_idx < len(strikes) - 1:
                otm_call_iv = iv_surface[strikes[atm_idx + 1]].get("call_iv")
            
            if otm_put_iv and otm_call_iv:
                skew = otm_put_iv - otm_call_iv
                return {
                    "skew_magnitude": abs(skew),
                    "skew_direction": "put" if skew > 0 else "call",
                    "atm_iv": atm_iv,
                }
            
            return {"atm_iv": atm_iv}
        
        except Exception as e:
            logger.warning(f"Error calculating IV skew: {e}")
            return {}
