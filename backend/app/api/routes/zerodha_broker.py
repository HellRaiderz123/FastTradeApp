"""
Zerodha Positions API endpoint
Fetches live positions from Zerodha broker
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import logging

from app.core.broker.zerodha.client import get_kite_client
from app.core.broker.registry import get_registry, get_active_broker, BrokerUnsupportedError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/zerodha", tags=["Zerodha"])


def _require_zerodha_capability(capability: str):
    """Check active broker supports the capability, raise 400 with clear message if not."""
    broker = get_active_broker()
    try:
        get_registry().require(broker, capability)
    except BrokerUnsupportedError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/positions")
def get_zerodha_positions() -> Dict[str, Any]:
    _require_zerodha_capability("positions")
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
    _require_zerodha_capability("order_book")
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
    _require_zerodha_capability("holdings")
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
