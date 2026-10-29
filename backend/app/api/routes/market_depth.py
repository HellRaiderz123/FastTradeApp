"""
Market Depth / Order Book API — broker-agnostic.

Fetches real Level 2 data from the active broker (Zerodha or INDMoney).
INDstocks endpoint: GET /market/quotes/mkt
Zerodha endpoint:   kite.quote() depth field

Set ACTIVE_BROKER=ZERODHA or ACTIVE_BROKER=INDMONEY in backend/.env.
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from typing import Any, Dict
import logging

from app.services.market_data_service import get_market_data_service, MarketDepth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market-depth", tags=["market_depth"])


def _depth_to_dict(depth: MarketDepth) -> Dict[str, Any]:
    """Serialise a MarketDepth object to the API response shape."""
    bids = [
        {"price": lvl.price, "quantity": lvl.quantity, "orders": lvl.orders}
        for lvl in depth.bids
    ]
    asks = [
        {"price": lvl.price, "quantity": lvl.quantity, "orders": lvl.orders}
        for lvl in depth.asks
    ]

    # Cumulative quantities for depth-chart visualisation
    cum = 0
    for b in bids:
        cum += b["quantity"]
        b["cumulative_qty"] = cum

    cum = 0
    for a in asks:
        cum += a["quantity"]
        a["cumulative_qty"] = cum

    best_bid = bids[0]["price"] if bids and bids[0]["price"] else 0.0
    best_ask = asks[0]["price"] if asks and asks[0]["price"] else 0.0
    spread = round(best_ask - best_bid, 2) if best_bid and best_ask else 0.0
    spread_pct = round(spread / best_bid * 100, 4) if best_bid else 0.0

    total_bid_qty = depth.total_buy_qty or sum(b["quantity"] for b in bids)
    total_ask_qty = depth.total_sell_qty or sum(a["quantity"] for a in asks)
    total = total_bid_qty + total_ask_qty
    imbalance = round((total_bid_qty - total_ask_qty) / total * 100, 2) if total else 0.0

    return {
        "symbol": depth.symbol,
        "timestamp": datetime.now().isoformat(),
        "spot_price": round(depth.ltp, 2),
        "best_bid": round(best_bid, 2),
        "best_ask": round(best_ask, 2),
        "spread": spread,
        "spread_percentage": spread_pct,
        "bids": bids,
        "asks": asks,
        "total_bid_qty": total_bid_qty,
        "total_ask_qty": total_ask_qty,
        "total_bid_orders": sum(b["orders"] for b in bids),
        "total_ask_orders": sum(a["orders"] for a in asks),
        "imbalance": imbalance,
        "imbalance_direction": "bullish" if imbalance > 5 else "bearish" if imbalance < -5 else "neutral",
        "volume": depth.volume,
        "open": depth.open,
        "high": depth.high,
        "low": depth.low,
        "prev_close": depth.prev_close,
        "oi": depth.oi,
        "data_source": depth.data_source,
    }


@router.get("/depth/{symbol}")
async def get_market_depth(symbol: str, exchange: str = "NSE"):
    """
    Get Level 2 market depth / order book for a symbol.

    Uses the active broker (ACTIVE_BROKER env var).
    - Zerodha: depth from kite.quote() depth field
    - INDMoney: depth from /market/quotes/mkt endpoint
    """
    try:
        symbol = symbol.upper().strip()
        exchange = exchange.upper().strip()

        svc = get_market_data_service()
        depth = svc.get_market_depth(symbol, exchange)

        if not depth:
            active = svc.get_active_adapter()
            broker_name = active.name if active else "any broker"
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Could not fetch market depth for {symbol} from {broker_name}. "
                    "Ensure your broker session is active (check Settings)."
                ),
            )

        return _depth_to_dict(depth)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Market depth error for %s: %s", symbol, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch market depth: {e}")


@router.get("/depth/{symbol}/analysis")
async def get_depth_analysis(symbol: str, exchange: str = "NSE"):
    """
    Advanced depth analysis: spread rating, liquidity, order flow signal,
    support/resistance from the live order book.
    """
    try:
        symbol = symbol.upper().strip()
        svc = get_market_data_service()
        depth = svc.get_market_depth(symbol, exchange.upper())

        if not depth:
            raise HTTPException(status_code=503, detail=f"Could not fetch depth for {symbol}")

        d = _depth_to_dict(depth)

        avg_bid_size = d["total_bid_qty"] / len(d["bids"]) if d["bids"] else 0
        avg_ask_size = d["total_ask_qty"] / len(d["asks"]) if d["asks"] else 0
        max_bid = max(d["bids"], key=lambda x: x["quantity"], default=None)
        max_ask = max(d["asks"], key=lambda x: x["quantity"], default=None)
        pressure = d["imbalance"]
        signal = (
            "Strong Buy" if pressure > 15 else
            "Buy" if pressure > 5 else
            "Strong Sell" if pressure < -15 else
            "Sell" if pressure < -5 else
            "Neutral"
        )

        return {
            "symbol": d["symbol"],
            "timestamp": d["timestamp"],
            "spot_price": d["spot_price"],
            "data_source": d["data_source"],
            "spread_analysis": {
                "absolute": d["spread"],
                "percentage": d["spread_percentage"],
                "rating": "tight" if d["spread_percentage"] < 0.01 else "normal" if d["spread_percentage"] < 0.05 else "wide",
            },
            "liquidity": {
                "total_bid_qty": d["total_bid_qty"],
                "total_ask_qty": d["total_ask_qty"],
                "avg_bid_size": round(avg_bid_size, 2),
                "avg_ask_size": round(avg_ask_size, 2),
                "max_bid_level": max_bid,
                "max_ask_level": max_ask,
            },
            "order_flow": {
                "imbalance": pressure,
                "direction": d["imbalance_direction"],
                "signal": signal,
            },
            "support_resistance": {
                "support": d["bids"][0]["price"] if d["bids"] else None,
                "resistance": d["asks"][0]["price"] if d["asks"] else None,
                "strong_support": max_bid["price"] if max_bid else None,
                "strong_resistance": max_ask["price"] if max_ask else None,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Depth analysis error for %s: %s", symbol, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to analyze depth: {e}")


@router.get("/depth/{symbol}/snapshot")
async def get_depth_snapshot(symbol: str, exchange: str = "NSE", interval: int = 5):
    """
    Returns `interval` snapshots of the current depth (all fetched live).
    Historical depth snapshots are not available from either broker API;
    this endpoint returns the current live book repeated with staggered timestamps
    for UI compatibility.
    """
    try:
        symbol = symbol.upper().strip()
        svc = get_market_data_service()
        depth = svc.get_market_depth(symbol, exchange.upper())

        if not depth:
            raise HTTPException(status_code=503, detail=f"Could not fetch depth for {symbol}")

        current = _depth_to_dict(depth)
        snapshots = []
        for i in range(interval, 0, -1):
            snap = dict(current)
            snap["timestamp"] = (datetime.now() - timedelta(minutes=i)).strftime("%Y-%m-%dT%H:%M:%S")
            snapshots.append(snap)
        snapshots.append(current)

        return {"symbol": symbol, "snapshots": snapshots, "count": len(snapshots)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Depth snapshot error for %s: %s", symbol, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch depth snapshots: {e}")
