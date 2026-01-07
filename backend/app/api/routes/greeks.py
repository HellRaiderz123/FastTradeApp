"""
Greeks Calculation API Endpoints
Calculates and aggregates Greeks for option strategies
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, timedelta
import logging
from app.core.indicators.greeks import GreeksCalculator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/greeks", tags=["Greeks"])


# ====== SCHEMAS ======

class OptionLegInput(BaseModel):
    """Input schema for a single option leg"""
    type: str  # BUY or SELL
    option_type: str  # CE or PE (call or put)
    strike: float
    spot: float
    expiry_days: int  # days to expiration
    volatility: float  # IV as percentage (e.g., 20.5 for 20.5%)
    quantity: int = 1
    premium: Optional[float] = None  # optional, for validation


class GreeksCalculationRequest(BaseModel):
    """Request body for Greeks calculation"""
    legs: List[OptionLegInput]
    spot: Optional[float] = None  # override spot price for all legs
    rate: float = 5.0  # risk-free rate in %


class GreeksCalculationResponse(BaseModel):
    """Response with calculated Greeks"""
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    premium: float
    max_profit: Optional[float] = None
    max_loss: Optional[float] = None
    legs_details: List[dict] = []


# ====== ENDPOINTS ======

@router.post("/calculate", response_model=GreeksCalculationResponse)
def calculate_greeks(request: GreeksCalculationRequest):
    """
    Calculate aggregated Greeks for a multi-leg option strategy.
    
    Args:
        request: GreeksCalculationRequest with list of option legs
    
    Returns:
        GreeksCalculationResponse with Delta, Gamma, Theta, Vega, Rho
    
    Example:
        {
            "legs": [
                {
                    "type": "BUY",
                    "option_type": "CE",
                    "strike": 26000,
                    "spot": 26150,
                    "expiry_days": 7,
                    "volatility": 20.5,
                    "quantity": 1
                }
            ],
            "spot": 26150,
            "rate": 5.0
        }
    """
    try:
        legs_details = []
        total_delta = 0
        total_gamma = 0
        total_theta = 0
        total_vega = 0
        total_rho = 0
        total_premium = 0
        
        # Override spot price if provided globally
        spot = request.spot or (request.legs[0].spot if request.legs else None)
        
        if not spot:
            raise ValueError("Spot price not provided")
        
        # Calculate expiry date
        today = date.today()
        
        for leg in request.legs:
            try:
                # Use GreeksCalculator properly
                leg_spot = request.spot or leg.spot
                volatility = leg.volatility / 100.0  # Convert percentage to decimal
                
                # Calculate expiry date from days_to_expiry
                expiry_date = today + timedelta(days=leg.expiry_days)
                
                # Create calculator for this leg
                calculator = GreeksCalculator(
                    spot=leg_spot,
                    strike=leg.strike,
                    expiry=expiry_date,
                    volatility=volatility,
                    option_type=leg.option_type.upper()  # "CE" or "PE"
                )
                
                # Calculate all Greeks for this leg
                greeks = calculator.calculate_all()
                
                # Apply sign based on BUY/SELL
                sign = 1 if leg.type.upper() == "BUY" else -1
                quantity = leg.quantity
                
                # Accumulate Greeks
                total_delta += greeks['delta'] * sign * quantity
                total_gamma += greeks['gamma'] * sign * quantity
                total_theta += greeks['theta'] * sign * quantity  # Already daily from calculator
                total_vega += greeks['vega'] * sign * quantity
                total_rho += greeks['rho'] * sign * quantity
                total_premium += greeks['premium'] * sign * quantity
                
                # Store leg details
                legs_details.append({
                    "strike": leg.strike,
                    "type": leg.type,
                    "option_type": leg.option_type,
                    "quantity": quantity,
                    "delta": round(greeks['delta'], 4),
                    "gamma": round(greeks['gamma'], 6),
                    "theta": round(greeks['theta'], 2),
                    "vega": round(greeks['vega'], 2),
                    "rho": round(greeks['rho'], 2),
                    "premium": round(greeks['premium'], 2),
                })
            
            except Exception as e:
                logger.error(f"Error calculating Greeks for leg {leg}: {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Error calculating Greeks for leg: {str(e)}"
                )
        
        return GreeksCalculationResponse(
            delta=round(total_delta, 4),
            gamma=round(total_gamma, 6),
            theta=round(total_theta, 2),
            vega=round(total_vega, 2),
            rho=round(total_rho, 2),
            premium=round(total_premium, 2),
            legs_details=legs_details
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Greeks calculation error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Greeks calculation failed: {str(e)}"
        )


@router.post("/single")
def calculate_single_greek(leg: OptionLegInput):
    """
    Calculate Greeks for a single option leg (CE or PE).
    
    Args:
        leg: Single option leg details
    
    Returns:
        Greeks for that single leg
    """
    try:
        today = date.today()
        expiry_date = today + timedelta(days=leg.expiry_days)
        volatility = leg.volatility / 100.0
        
        calculator = GreeksCalculator(
            spot=leg.spot,
            strike=leg.strike,
            expiry=expiry_date,
            volatility=volatility,
            option_type=leg.option_type.upper()
        )
        
        greeks = calculator.calculate_all()
        
        return {
            "strike": leg.strike,
            "delta": round(greeks['delta'], 4),
            "gamma": round(greeks['gamma'], 6),
            "theta": round(greeks['theta'], 2),
            "vega": round(greeks['vega'], 2),
            "rho": round(greeks['rho'], 2),
            "premium": round(greeks['premium'], 2),
        }
    
    except Exception as e:
        logger.error(f"Single Greeks calculation error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Greeks calculation failed: {str(e)}"
        )
