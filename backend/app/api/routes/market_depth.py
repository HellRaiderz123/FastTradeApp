"""
Market Depth / Order Book API
Level 2 market data with bid/ask ladder, spread analysis
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
import logging
import random

from app.services.zerodha import KiteConnectService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market-depth", tags=["market_depth"])

kite_service = KiteConnectService()


def generate_mock_market_depth(symbol: str, spot_price: float) -> Dict[str, Any]:
    """Generate realistic mock market depth data"""
    
    # Calculate bid/ask spread (0.05% - 0.2% of price)
    spread_pct = random.uniform(0.0005, 0.002)
    spread = spot_price * spread_pct
    
    mid_price = spot_price
    best_bid = mid_price - (spread / 2)
    best_ask = mid_price + (spread / 2)
    
    # Generate 5 levels of bids (descending prices)
    bids = []
    current_bid = best_bid
    total_bid_qty = 0
    
    for i in range(5):
        price = round(current_bid - (i * 0.5), 2)
        quantity = random.randint(50, 500) * 100  # Lots of 100
        orders = random.randint(5, 25)
        
        bids.append({
            "price": price,
            "quantity": quantity,
            "orders": orders,
        })
        total_bid_qty += quantity
        current_bid = price
    
    # Generate 5 levels of asks (ascending prices)
    asks = []
    current_ask = best_ask
    total_ask_qty = 0
    
    for i in range(5):
        price = round(current_ask + (i * 0.5), 2)
        quantity = random.randint(50, 500) * 100
        orders = random.randint(5, 25)
        
        asks.append({
            "price": price,
            "quantity": quantity,
            "orders": orders,
        })
        total_ask_qty += quantity
        current_ask = price
    
    # Calculate cumulative quantities for depth visualization
    cumulative_bid_qty = 0
    for bid in bids:
        cumulative_bid_qty += bid["quantity"]
        bid["cumulative_qty"] = cumulative_bid_qty
    
    cumulative_ask_qty = 0
    for ask in asks:
        cumulative_ask_qty += ask["quantity"]
        ask["cumulative_qty"] = cumulative_ask_qty
    
    # Depth metrics
    bid_ask_spread = best_ask - best_bid
    spread_percentage = (bid_ask_spread / mid_price) * 100
    
    # Order flow imbalance (positive = bullish, negative = bearish)
    imbalance = (total_bid_qty - total_ask_qty) / (total_bid_qty + total_ask_qty) * 100
    
    return {
        "symbol": symbol,
        "timestamp": "2026-02-07T10:30:00",
        "spot_price": round(mid_price, 2),
        "best_bid": round(best_bid, 2),
        "best_ask": round(best_ask, 2),
        "spread": round(bid_ask_spread, 2),
        "spread_percentage": round(spread_percentage, 4),
        "bids": bids,
        "asks": asks,
        "total_bid_qty": total_bid_qty,
        "total_ask_qty": total_ask_qty,
        "total_bid_orders": sum(b["orders"] for b in bids),
        "total_ask_orders": sum(a["orders"] for a in asks),
        "imbalance": round(imbalance, 2),
        "imbalance_direction": "bullish" if imbalance > 5 else "bearish" if imbalance < -5 else "neutral",
    }


@router.get("/depth/{symbol}")
async def get_market_depth(symbol: str):
    """
    Get Level 2 market depth / order book for a symbol
    
    Args:
        symbol: Stock symbol (e.g., RELIANCE, TCS)
    
    Returns:
        {
            "symbol": "RELIANCE",
            "spot_price": 2650.50,
            "best_bid": 2650.30,
            "best_ask": 2650.70,
            "spread": 0.40,
            "spread_percentage": 0.0151,
            "bids": [
                {"price": 2650.30, "quantity": 15000, "orders": 12, "cumulative_qty": 15000},
                {"price": 2649.80, "quantity": 22000, "orders": 18, "cumulative_qty": 37000},
                ...
            ],
            "asks": [
                {"price": 2650.70, "quantity": 18000, "orders": 15, "cumulative_qty": 18000},
                {"price": 2651.20, "quantity": 25000, "orders": 20, "cumulative_qty": 43000},
                ...
            ],
            "total_bid_qty": 85000,
            "total_ask_qty": 92000,
            "imbalance": -4.0,
            "imbalance_direction": "neutral"
        }
    """
    try:
        symbol = symbol.upper().strip()
        
        # Try to get real quote data
        spot_price = 2650.0  # Default
        
        if kite_service.kite:
            try:
                quote = kite_service.get_full_quote(symbol)
                if quote and "last_price" in quote:
                    spot_price = float(quote["last_price"])
                    
                    # If Zerodha provides depth data, use it
                    if "depth" in quote:
                        depth_data = quote["depth"]
                        
                        # Transform Zerodha depth format to our format
                        bids = []
                        asks = []
                        
                        if "buy" in depth_data:
                            cumulative_bid = 0
                            for level in depth_data["buy"]:
                                qty = level.get("quantity", 0)
                                cumulative_bid += qty
                                bids.append({
                                    "price": level.get("price", 0),
                                    "quantity": qty,
                                    "orders": level.get("orders", 1),
                                    "cumulative_qty": cumulative_bid,
                                })
                        
                        if "sell" in depth_data:
                            cumulative_ask = 0
                            for level in depth_data["sell"]:
                                qty = level.get("quantity", 0)
                                cumulative_ask += qty
                                asks.append({
                                    "price": level.get("price", 0),
                                    "quantity": qty,
                                    "orders": level.get("orders", 1),
                                    "cumulative_qty": cumulative_ask,
                                })
                        
                        # If we have real depth data, return it
                        if bids and asks:
                            total_bid_qty = sum(b["quantity"] for b in bids)
                            total_ask_qty = sum(a["quantity"] for a in asks)
                            best_bid = bids[0]["price"]
                            best_ask = asks[0]["price"]
                            spread = best_ask - best_bid
                            spread_pct = (spread / spot_price) * 100
                            imbalance = (total_bid_qty - total_ask_qty) / (total_bid_qty + total_ask_qty) * 100
                            
                            return {
                                "symbol": symbol,
                                "timestamp": quote.get("timestamp", ""),
                                "spot_price": spot_price,
                                "best_bid": best_bid,
                                "best_ask": best_ask,
                                "spread": round(spread, 2),
                                "spread_percentage": round(spread_pct, 4),
                                "bids": bids,
                                "asks": asks,
                                "total_bid_qty": total_bid_qty,
                                "total_ask_qty": total_ask_qty,
                                "total_bid_orders": sum(b["orders"] for b in bids),
                                "total_ask_orders": sum(a["orders"] for a in asks),
                                "imbalance": round(imbalance, 2),
                                "imbalance_direction": "bullish" if imbalance > 5 else "bearish" if imbalance < -5 else "neutral",
                            }
            except Exception as e:
                logger.warning(f"Failed to fetch real depth for {symbol}: {e}")
        
        # Fall back to mock data
        return generate_mock_market_depth(symbol, spot_price)
    
    except Exception as e:
        logger.error(f"Market depth error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch market depth: {str(e)}")


@router.get("/depth/{symbol}/snapshot")
async def get_depth_snapshot(symbol: str, interval: int = 5):
    """
    Get historical depth snapshots for the last N intervals
    
    Args:
        symbol: Stock symbol
        interval: Number of snapshots to return (default 5)
    
    Returns:
        List of depth snapshots showing how order book evolved
    """
    try:
        symbol = symbol.upper().strip()
        
        # Get current depth
        current_depth = await get_market_depth(symbol)
        spot_price = current_depth["spot_price"]
        
        # Generate historical snapshots (mock data)
        snapshots = []
        
        for i in range(interval, 0, -1):
            # Vary price slightly for historical snapshots
            historical_price = spot_price * (1 + random.uniform(-0.002, 0.002))
            snapshot = generate_mock_market_depth(symbol, historical_price)
            
            # Add timestamp (i minutes ago)
            from datetime import datetime, timedelta
            ts = datetime.now() - timedelta(minutes=i)
            snapshot["timestamp"] = ts.strftime("%Y-%m-%dT%H:%M:%S")
            
            snapshots.append(snapshot)
        
        # Add current snapshot
        snapshots.append(current_depth)
        
        return {
            "symbol": symbol,
            "snapshots": snapshots,
            "count": len(snapshots),
        }
    
    except Exception as e:
        logger.error(f"Depth snapshot error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch depth snapshots: {str(e)}")


@router.get("/depth/{symbol}/analysis")
async def get_depth_analysis(symbol: str):
    """
    Get advanced depth analysis metrics
    
    Returns:
        - Order book pressure (bid/ask dominance)
        - Average order size
        - Price levels with maximum liquidity
        - Support/resistance from order book
    """
    try:
        depth = await get_market_depth(symbol)
        
        # Calculate analysis metrics
        avg_bid_size = depth["total_bid_qty"] / len(depth["bids"]) if depth["bids"] else 0
        avg_ask_size = depth["total_ask_qty"] / len(depth["asks"]) if depth["asks"] else 0
        
        avg_bid_orders = depth["total_bid_orders"] / len(depth["bids"]) if depth["bids"] else 0
        avg_ask_orders = depth["total_ask_orders"] / len(depth["asks"]) if depth["asks"] else 0
        
        # Find max liquidity levels
        max_bid_level = max(depth["bids"], key=lambda x: x["quantity"]) if depth["bids"] else None
        max_ask_level = max(depth["asks"], key=lambda x: x["quantity"]) if depth["asks"] else None
        
        # Order book pressure
        pressure = depth["imbalance"]
        pressure_signal = "Strong Buy" if pressure > 15 else "Buy" if pressure > 5 else "Neutral" if abs(pressure) <= 5 else "Sell" if pressure > -15 else "Strong Sell"
        
        return {
            "symbol": depth["symbol"],
            "timestamp": depth["timestamp"],
            "spot_price": depth["spot_price"],
            "spread_analysis": {
                "absolute": depth["spread"],
                "percentage": depth["spread_percentage"],
                "rating": "tight" if depth["spread_percentage"] < 0.01 else "normal" if depth["spread_percentage"] < 0.05 else "wide",
            },
            "liquidity": {
                "total_bid_qty": depth["total_bid_qty"],
                "total_ask_qty": depth["total_ask_qty"],
                "avg_bid_size": round(avg_bid_size, 2),
                "avg_ask_size": round(avg_ask_size, 2),
                "max_bid_level": max_bid_level,
                "max_ask_level": max_ask_level,
            },
            "order_flow": {
                "imbalance": pressure,
                "direction": depth["imbalance_direction"],
                "signal": pressure_signal,
                "avg_bid_orders": round(avg_bid_orders, 2),
                "avg_ask_orders": round(avg_ask_orders, 2),
            },
            "support_resistance": {
                "support": depth["bids"][0]["price"] if depth["bids"] else None,
                "resistance": depth["asks"][0]["price"] if depth["asks"] else None,
                "strong_support": max_bid_level["price"] if max_bid_level else None,
                "strong_resistance": max_ask_level["price"] if max_ask_level else None,
            },
        }
    
    except Exception as e:
        logger.error(f"Depth analysis error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to analyze depth: {str(e)}")
