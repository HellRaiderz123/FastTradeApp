from fastapi import APIRouter, HTTPException
from app.core.broker.zerodha.client import get_kite_client
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/account", tags=["Account"])


@router.get("/profile")
def get_account_profile():
    """
    Fetch account profile including available capital from Zerodha.
    
    Returns:
        {
            "user_id": str,
            "email": str,
            "phone": str,
            "capital": float,
            "equity": float,
            "net_worth": float,
            "margins_available": float
        }
    """
    try:
        kite = get_kite_client()
        
        # Get account profile
        profile = kite.profile()
        
        # Get account margins/balance info
        margins = kite.margins()
        
        # Extract equity details from margins
        equity = margins.get("equity", {})
        available = equity.get("available", {})
        utilised = equity.get("utilised", {})
        
        # Capital is JUST live_balance (don't add intraday_payin - it's the same money!)
        live_balance = available.get("live_balance", 0)
        
        # Get net equity value
        net_value = equity.get("net", 0)
        
        logger.info(f"📊 Account {profile.get('user_id')}: Capital = ₹{live_balance}, Net = ₹{net_value}")
        
        return {
            "user_id": profile.get("user_id"),
            "email": profile.get("email"),
            "phone": profile.get("phone"),
            "capital": live_balance,  # Real available capital
            "equity": net_value,  # Net equity value
            "net_worth": net_value,  # Same as equity for now
            "margins_available": live_balance,  # Available margin
            "live_balance": live_balance,
            "cash": available.get("cash", 0),
            "collateral": available.get("collateral", 0),
        }
    
    except RuntimeError as e:
        if "API key or access token missing" in str(e):
            logger.warning("Zerodha credentials not configured, using mock data for development")
            # Return mock data for development
            return {
                "user_id": "DEMO_USER",
                "email": "demo@zerodha.com",
                "phone": "+91-9876543210",
                "capital": 500000.0,  # Demo capital
                "live_balance": 500000.0,
                "intraday_payin": 0.0,
                "adhoc_margin": 0.0,
                "cash": 500000.0,
            }
        else:
            logger.error(f"Error fetching account profile: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch account profile: {str(e)}"
            )
    
    except Exception as e:
        logger.error(f"Error fetching account profile: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch account profile: {str(e)}"
        )


@router.get("/capital")
def get_available_capital():
    """
    Get available capital from Zerodha account.
    
    Returns:
        {
            "capital": float,
            "currency": str,
            "source": str
        }
    """
    try:
        kite = get_kite_client()
        margins = kite.margins()
        
        # Extract capital from equity data - just use live_balance
        equity = margins.get("equity", {})
        available = equity.get("available", {})
        live_balance = available.get("live_balance", 0)
        
        logger.info(f"💰 Available Capital: ₹{live_balance}")
        
        return {
            "capital": live_balance,
            "currency": "INR",
            "source": "zerodha",
        }
    
    except RuntimeError as e:
        if "API key or access token missing" in str(e):
            logger.warning("Zerodha credentials not configured, using mock data for development")
            # Return mock data for development
            return {
                "capital": 100000.0,
                "currency": "INR",
                "source": "mock",
            }
        else:
            logger.error(f"Error fetching capital: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch capital: {str(e)}"
            )
    
    except Exception as e:
        logger.error(f"Error fetching capital: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch capital: {str(e)}"
        )
