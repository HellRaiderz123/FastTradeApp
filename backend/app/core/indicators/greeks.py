"""
Greeks Calculator - Black-Scholes Model
Calculates Delta, Gamma, Theta, Vega, Rho for options
"""

import logging
import math
from typing import Dict, Optional, Tuple
from datetime import datetime, date
from scipy.stats import norm

logger = logging.getLogger(__name__)


class GreeksCalculator:
    """Calculate option Greeks using Black-Scholes model"""
    
    # Risk-free rate (current market rate for Indian market)
    RISK_FREE_RATE = 0.065  # 6.5% per annum
    
    # Dividend yield for NIFTY (approximately)
    DIVIDEND_YIELD = 0.015  # 1.5% per annum
    
    def __init__(
        self,
        spot: float,
        strike: float,
        expiry: date,
        volatility: float,
        option_type: str = "CE",  # "CE" or "PE"
    ):
        """
        Initialize Greeks calculator
        
        Args:
            spot: Current spot price
            strike: Strike price
            expiry: Expiry date
            volatility: Annualized volatility (e.g., 0.25 for 25%)
            option_type: "CE" (Call) or "PE" (Put)
        """
        self.spot = spot
        self.strike = strike
        self.expiry = expiry
        self.volatility = volatility
        self.option_type = option_type.upper()
        
        # Calculate time to expiry in years
        today = date.today()
        days_to_expiry = (expiry - today).days
        self.tau = max(days_to_expiry / 365.0, 0.001)  # Avoid zero
        
        logger.debug(f"Greeks for {option_type} {strike} | Spot: {spot} | Vol: {volatility*100:.1f}% | TTM: {self.tau*365:.0f} days")
    
    def calculate_all(self) -> Dict[str, float]:
        """Calculate all Greeks"""
        try:
            return {
                "delta": self._calculate_delta(),
                "gamma": self._calculate_gamma(),
                "theta": self._calculate_theta(),
                "vega": self._calculate_vega(),
                "rho": self._calculate_rho(),
                "premium": self._calculate_premium(),
            }
        except Exception as e:
            logger.error(f"Error calculating Greeks: {e}")
            return {
                "delta": 0.0,
                "gamma": 0.0,
                "theta": 0.0,
                "vega": 0.0,
                "rho": 0.0,
                "premium": 0.0,
            }
    
    def _calculate_d1_d2(self) -> Tuple[float, float]:
        """Calculate d1 and d2 for Black-Scholes"""
        try:
            d1 = (
                math.log(self.spot / self.strike)
                + (self.RISK_FREE_RATE - self.DIVIDEND_YIELD + 0.5 * self.volatility ** 2) * self.tau
            ) / (self.volatility * math.sqrt(self.tau))
            
            d2 = d1 - self.volatility * math.sqrt(self.tau)
            
            return d1, d2
        except:
            return 0.0, 0.0
    
    def _calculate_premium(self) -> float:
        """Calculate option premium using Black-Scholes"""
        try:
            d1, d2 = self._calculate_d1_d2()
            
            if self.option_type == "CE":
                # Call option
                premium = (
                    self.spot * math.exp(-self.DIVIDEND_YIELD * self.tau) * norm.cdf(d1)
                    - self.strike * math.exp(-self.RISK_FREE_RATE * self.tau) * norm.cdf(d2)
                )
            else:  # PE
                # Put option
                premium = (
                    self.strike * math.exp(-self.RISK_FREE_RATE * self.tau) * norm.cdf(-d2)
                    - self.spot * math.exp(-self.DIVIDEND_YIELD * self.tau) * norm.cdf(-d1)
                )
            
            return max(premium, 0.0)  # Premium cannot be negative
        except:
            return 0.0
    
    def _calculate_delta(self) -> float:
        """
        Delta: Rate of change of option price with respect to spot price
        Range: 0 to 1 for calls, -1 to 0 for puts
        """
        try:
            d1, _ = self._calculate_d1_d2()
            
            if self.option_type == "CE":
                delta = math.exp(-self.DIVIDEND_YIELD * self.tau) * norm.cdf(d1)
            else:  # PE
                delta = -math.exp(-self.DIVIDEND_YIELD * self.tau) * norm.cdf(-d1)
            
            return round(delta, 4)
        except:
            return 0.0
    
    def _calculate_gamma(self) -> float:
        """
        Gamma: Rate of change of delta
        Always positive for both calls and puts
        Highest when option is ATM
        """
        try:
            d1, _ = self._calculate_d1_d2()
            
            gamma = (
                math.exp(-self.DIVIDEND_YIELD * self.tau)
                * norm.pdf(d1)
                / (self.spot * self.volatility * math.sqrt(self.tau))
            )
            
            return round(gamma, 6)
        except:
            return 0.0
    
    def _calculate_theta(self) -> float:
        """
        Theta: Time decay per day
        Decay of option value as time passes (negative for long options)
        """
        try:
            d1, d2 = self._calculate_d1_d2()
            sqrt_tau = math.sqrt(self.tau)
            
            if self.option_type == "CE":
                # Call theta
                theta = (
                    -self.spot
                    * math.exp(-self.DIVIDEND_YIELD * self.tau)
                    * norm.pdf(d1)
                    * self.volatility
                    / (2 * sqrt_tau)
                    + self.DIVIDEND_YIELD
                    * self.spot
                    * math.exp(-self.DIVIDEND_YIELD * self.tau)
                    * norm.cdf(d1)
                    - self.RISK_FREE_RATE
                    * self.strike
                    * math.exp(-self.RISK_FREE_RATE * self.tau)
                    * norm.cdf(d2)
                )
            else:  # PE
                # Put theta
                theta = (
                    -self.spot
                    * math.exp(-self.DIVIDEND_YIELD * self.tau)
                    * norm.pdf(d1)
                    * self.volatility
                    / (2 * sqrt_tau)
                    - self.DIVIDEND_YIELD
                    * self.spot
                    * math.exp(-self.DIVIDEND_YIELD * self.tau)
                    * norm.cdf(-d1)
                    + self.RISK_FREE_RATE
                    * self.strike
                    * math.exp(-self.RISK_FREE_RATE * self.tau)
                    * norm.cdf(-d2)
                )
            
            # Convert to per-day theta
            theta_per_day = theta / 365.0
            return round(theta_per_day, 6)
        except:
            return 0.0
    
    def _calculate_vega(self) -> float:
        """
        Vega: Sensitivity to volatility change (per 1% change in vol)
        Positive for both calls and puts
        """
        try:
            d1, _ = self._calculate_d1_d2()
            
            vega = (
                self.spot
                * math.exp(-self.DIVIDEND_YIELD * self.tau)
                * norm.pdf(d1)
                * math.sqrt(self.tau)
                / 100  # Per 1% volatility change
            )
            
            return round(vega, 6)
        except:
            return 0.0
    
    def _calculate_rho(self) -> float:
        """
        Rho: Sensitivity to interest rate changes (per 1% change)
        Positive for calls, negative for puts
        """
        try:
            _, d2 = self._calculate_d1_d2()
            
            if self.option_type == "CE":
                rho = (
                    self.strike
                    * self.tau
                    * math.exp(-self.RISK_FREE_RATE * self.tau)
                    * norm.cdf(d2)
                    / 100
                )
            else:  # PE
                rho = (
                    -self.strike
                    * self.tau
                    * math.exp(-self.RISK_FREE_RATE * self.tau)
                    * norm.cdf(-d2)
                    / 100
                )
            
            return round(rho, 6)
        except:
            return 0.0


def calculate_weighted_greeks(
    spot: float,
    atm_strike: float,
    expiry: date,
    volatility: float,
    option_chain: Dict = None,
) -> Dict[str, float]:
    """
    Calculate weighted Greeks for a portfolio
    
    Args:
        spot: Current spot price
        atm_strike: ATM strike
        expiry: Expiry date
        volatility: Current market volatility
        option_chain: Option chain data (for multiple strikes)
    
    Returns:
        Aggregated Greeks for the portfolio
    """
    try:
        # For single strike (ATM), calculate both CE and PE
        if not option_chain:
            ce_calc = GreeksCalculator(spot, atm_strike, expiry, volatility, "CE")
            pe_calc = GreeksCalculator(spot, atm_strike, expiry, volatility, "PE")
            
            ce_greeks = ce_calc.calculate_all()
            pe_greeks = pe_calc.calculate_all()
            
            return {
                "call_greeks": ce_greeks,
                "put_greeks": pe_greeks,
                "total_delta": ce_greeks["delta"] - pe_greeks["delta"],
                "total_gamma": ce_greeks["gamma"] + pe_greeks["gamma"],
                "total_theta": ce_greeks["theta"] + pe_greeks["theta"],
                "total_vega": ce_greeks["vega"] + pe_greeks["vega"],
            }
        else:
            # For multiple strikes, weight by OI
            total_delta = 0.0
            total_gamma = 0.0
            total_theta = 0.0
            total_vega = 0.0
            total_oi = 0.0
            
            for strike_data in option_chain:
                strike = strike_data.get("strike")
                oi = strike_data.get("oi", 0)
                
                if oi == 0:
                    continue
                
                calc = GreeksCalculator(spot, strike, expiry, volatility, "CE")
                greeks = calc.calculate_all()
                
                total_delta += greeks["delta"] * oi
                total_gamma += greeks["gamma"] * oi
                total_theta += greeks["theta"] * oi
                total_vega += greeks["vega"] * oi
                total_oi += oi
            
            if total_oi == 0:
                return {
                    "total_delta": 0.0,
                    "total_gamma": 0.0,
                    "total_theta": 0.0,
                    "total_vega": 0.0,
                }
            
            return {
                "total_delta": round(total_delta / total_oi, 4),
                "total_gamma": round(total_gamma / total_oi, 6),
                "total_theta": round(total_theta / total_oi, 6),
                "total_vega": round(total_vega / total_oi, 6),
            }
    
    except Exception as e:
        logger.error(f"Error calculating weighted Greeks: {e}")
        return {
            "total_delta": 0.0,
            "total_gamma": 0.0,
            "total_theta": 0.0,
            "total_vega": 0.0,
        }


def get_greeks_interpretation(greeks: Dict[str, float]) -> Dict[str, str]:
    """
    Get human-readable interpretation of Greeks
    """
    delta = greeks.get("delta", 0)
    gamma = greeks.get("gamma", 0)
    theta = greeks.get("theta", 0)
    vega = greeks.get("vega", 0)
    
    interpretations = {}
    
    # Delta interpretation
    if abs(delta) < 0.25:
        interpretations["delta"] = f"Low sensitivity ({delta:.2f})"
    elif abs(delta) < 0.75:
        interpretations["delta"] = f"Moderate sensitivity ({delta:.2f})"
    else:
        interpretations["delta"] = f"High sensitivity ({delta:.2f})"
    
    # Gamma interpretation
    if gamma < 0.01:
        interpretations["gamma"] = "Low gamma (slow delta change)"
    elif gamma < 0.05:
        interpretations["gamma"] = "Moderate gamma"
    else:
        interpretations["gamma"] = "High gamma (fast delta change)"
    
    # Theta interpretation
    if theta > 0:
        interpretations["theta"] = f"Positive theta (+{theta:.6f}, benefits from time decay)"
    else:
        interpretations["theta"] = f"Negative theta ({theta:.6f}, loses to time decay)"
    
    # Vega interpretation
    if vega > 0.01:
        interpretations["vega"] = f"High vega sensitivity ({vega:.6f})"
    else:
        interpretations["vega"] = f"Low vega sensitivity ({vega:.6f})"
    
    return interpretations
