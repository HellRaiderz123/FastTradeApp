"""
Zerodha Positions API endpoint
Fetches live positions from Zerodha broker
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import logging

from app.core.broker.zerodha.client import get_kite_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/zerodha", tags=["Zerodha"])


@router.get("/positions")
def get_zerodha_positions() -> Dict[str, Any]:
    """
    Fetch live positions from Zerodha broker
    
    Returns:
        {
            "net": [
                {
                    "tradingsymbol": "NIFTY24FEB25000PE",
                    "quantity": 1,
                    "used_quantity": 1,
                    "average_price": 150.00,
                    "last_price": 145.50,
                    "close_price": 152.00,
                    "pnl": -4.50,
                    "p_l": -4.50,
                    "m2m": -4.50,
                    "unrealised": -4.50,
                    "realised": 0.00,
                    "multiplier": 100,
                    ...
                },
                ...
            ]
        }
    """
    try:
        kite = get_kite_client()
        positions = kite.positions()
        logger.info(f"✅ Fetched {len(positions.get('net', []))} positions from Zerodha")
        return positions
    except Exception as e:
        logger.error(f"❌ Error fetching Zerodha positions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch positions from Zerodha: {str(e)}"
        )


@router.get("/orders")
def get_zerodha_orders() -> List[Dict[str, Any]]:
    """
    Fetch all orders (active and completed) from Zerodha
    
    Returns list of orders with status, quantity, price, etc.
    """
    try:
        kite = get_kite_client()
        orders = kite.orders()
        logger.info(f"✅ Fetched {len(orders)} orders from Zerodha")
        return orders
    except Exception as e:
        logger.error(f"❌ Error fetching Zerodha orders: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch orders from Zerodha: {str(e)}"
        )


@router.get("/holdings")
def get_zerodha_holdings() -> List[Dict[str, Any]]:
    """
    Fetch holdings (stocks held overnight) from Zerodha
    
    Returns list of holdings with quantity, LTP, P&L, etc.
    """
    try:
        kite = get_kite_client()
        holdings = kite.holdings()
        logger.info(f"✅ Fetched {len(holdings)} holdings from Zerodha")
        return holdings
    except Exception as e:
        logger.error(f"❌ Error fetching Zerodha holdings: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch holdings from Zerodha: {str(e)}"
        )
