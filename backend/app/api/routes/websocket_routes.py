"""
WebSocket Routes
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
import logging

from app.db.session import SessionLocal
from app.services.websocket import manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.websocket("/live")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates
    
    Client will receive:
    - MTM updates (every 5s)
    - Position updates
    - Trade executions
    - Notifications
    - System status (every 10s)
    """
    await manager.connect(websocket)
    
    try:
        # Send initial connection success
        await manager.send_personal_message({
            "type": "connected",
            "message": "WebSocket connected successfully",
            "timestamp": "now"
        }, websocket)
        
        # Keep connection alive
        while True:
            # Receive messages from client (heartbeat, commands, etc.)
            data = await websocket.receive_text()
            
            # Echo back for heartbeat
            await manager.send_personal_message({
                "type": "heartbeat",
                "data": data
            }, websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        manager.disconnect(websocket)


@router.get("/connections")
def get_connection_count():
    """Get number of active WebSocket connections"""
    return {
        "success": True,
        "connections": manager.get_connection_count()
    }


@router.websocket("/quotes")
async def websocket_quotes(websocket: WebSocket, symbols: str = ""):
    """
    WebSocket endpoint for real-time stock quotes
    
    Client connects with: /ws/quotes?symbols=RELIANCE,TCS,INFY
    
    Server sends updates every 1-2 seconds:
    {
        "type": "quote_update",
        "data": {
            "RELIANCE": {
                "ltp": 2875.40,
                "change": 12.50,
                "change_percent": 0.44,
                "volume": 5234567
            },
            ...
        },
        "timestamp": "2026-02-07T15:30:45"
    }
    """
    import asyncio
    from datetime import datetime
    from app.services.zerodha import KiteConnectService
    
    await websocket.accept()
    
    # Parse symbols
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    
    if not symbol_list:
        await websocket.send_json({
            "type": "error",
            "message": "No symbols provided. Use ?symbols=RELIANCE,TCS,INFY"
        })
        await websocket.close()
        return
    
    logger.info(f"Quote WebSocket connected for symbols: {symbol_list}")
    
    # Initialize Zerodha service
    kite_service = KiteConnectService()
    
    try:
        await websocket.send_json({
            "type": "connected",
            "symbols": symbol_list,
            "message": f"Streaming quotes for {len(symbol_list)} symbols"
        })
        
        # Send quote updates every 2 seconds
        while True:
            quotes_data = {}
            
            for symbol in symbol_list:
                try:
                    # Fetch live data from Zerodha using same logic as bulk-quotes
                    data = kite_service.get_full_quote(symbol)
                    
                    if data and "last_price" in data and data["last_price"] is not None:
                        # Use live data
                        ltp = float(data["last_price"])
                        ohlc = data.get("ohlc", {})
                        prev_close = ohlc.get("close", ltp)
                        change = ltp - prev_close
                        change_percent = (change / prev_close * 100) if prev_close else 0
                        
                        quotes_data[symbol] = {
                            "ltp": round(ltp, 2),
                            "change": round(change, 2),
                            "change_percent": round(change_percent, 2),
                            "volume": data.get("volume", 0),
                            "last_traded_time": datetime.now().isoformat(),
                            "live": True
                        }
                    else:
                        # Fallback to last known price (not simulated)
                        logger.debug(f"No live data for {symbol}, data unavailable")
                        quotes_data[symbol] = {
                            "ltp": 0.0,
                            "change": 0.0,
                            "change_percent": 0.0,
                            "volume": 0,
                            "last_traded_time": datetime.now().isoformat(),
                            "live": False,
                            "error": "Market closed or data unavailable"
                        }
                    
                except Exception as e:
                    logger.warning(f"Error fetching {symbol}: {e}")
                    # Return error state
                    quotes_data[symbol] = {
                        "ltp": 0.0,
                        "change": 0.0,
                        "change_percent": 0.0,
                        "volume": 0,
                        "last_traded_time": datetime.now().isoformat(),
                        "live": False,
                        "error": str(e)
                    }
            
            # Send update
            await websocket.send_json({
                "type": "quote_update",
                "data": quotes_data,
                "timestamp": datetime.now().isoformat()
            })
            
            await asyncio.sleep(2)  # Update every 2 seconds
    
    except WebSocketDisconnect:
        logger.info(f"Quote WebSocket disconnected for symbols: {symbol_list}")
    except Exception as e:
        logger.error(f"Quote WebSocket error: {e}", exc_info=True)
        try:
            await websocket.close()
        except:
            pass
