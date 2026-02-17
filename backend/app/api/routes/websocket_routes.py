"""
WebSocket Routes
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
import logging
import asyncio
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from app.db.session import SessionLocal
from app.services.websocket import manager
from app.services.zerodha import KiteConnectService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])

# Shared thread pool for blocking Zerodha API calls (avoids blocking event loop)
_quote_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="quote-worker")

# Singleton Kite service — reused across all WS connections
_kite_service: KiteConnectService | None = None


def _get_kite_service() -> KiteConnectService:
    """Get or create the singleton KiteConnectService."""
    global _kite_service
    if _kite_service is None:
        _kite_service = KiteConnectService()
    return _kite_service


def _fetch_bulk_quotes_sync(symbol_list: list[str]) -> dict:
    """
    Synchronous function that fetches bulk quotes.
    Runs in a thread pool so it doesn't block the async event loop.
    """
    kite_service = _get_kite_service()
    quotes_data = {}
    
    try:
        bulk_data = kite_service.get_bulk_quotes(symbol_list)
        
        for symbol in symbol_list:
            try:
                quote_entry = None
                if bulk_data:
                    nse_key = f"NSE:{symbol}"
                    if nse_key in bulk_data:
                        quote_entry = bulk_data[nse_key]
                    else:
                        for key, val in bulk_data.items():
                            if key.endswith(f":{symbol}") or key == symbol:
                                quote_entry = val
                                break
                
                if quote_entry and quote_entry.get("last_price") is not None:
                    ltp = float(quote_entry["last_price"])
                    ohlc = quote_entry.get("ohlc", {})
                    prev_close = ohlc.get("close", ltp)
                    change = ltp - prev_close
                    change_pct = (change / prev_close * 100) if prev_close else 0
                    
                    quotes_data[symbol] = {
                        "ltp": round(ltp, 2),
                        "change": round(change, 2),
                        "change_percent": round(change_pct, 2),
                        "volume": quote_entry.get("volume", 0),
                        "last_traded_time": datetime.now().isoformat(),
                        "live": True,
                    }
                else:
                    quotes_data[symbol] = {
                        "ltp": 0.0, "change": 0.0, "change_percent": 0.0,
                        "volume": 0, "last_traded_time": datetime.now().isoformat(),
                        "live": False, "error": "Market closed or data unavailable",
                    }
            except Exception as e:
                logger.warning(f"Error processing quote for {symbol}: {e}")
                quotes_data[symbol] = {
                    "ltp": 0.0, "change": 0.0, "change_percent": 0.0,
                    "volume": 0, "last_traded_time": datetime.now().isoformat(),
                    "live": False, "error": str(e),
                }
    except Exception as e:
        logger.error(f"Bulk quote fetch failed: {e}")
        for symbol in symbol_list:
            quotes_data[symbol] = {
                "ltp": 0.0, "change": 0.0, "change_percent": 0.0,
                "volume": 0, "last_traded_time": datetime.now().isoformat(),
                "live": False, "error": "Bulk fetch failed",
            }
    
    return quotes_data


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
    WebSocket endpoint for real-time stock quotes.
    
    Blocking Zerodha API calls are offloaded to a thread pool so
    the async event loop stays responsive and the connection
    doesn't timeout / flicker.
    """
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
    
    logger.info(f"Quote WebSocket connected for {len(symbol_list)} symbols: {symbol_list[:5]}...")
    
    try:
        await websocket.send_json({
            "type": "connected",
            "symbols": symbol_list,
            "message": f"Streaming quotes for {len(symbol_list)} symbols"
        })
        
        loop = asyncio.get_running_loop()
        
        while True:
            # Run blocking Zerodha call in thread pool — keeps event loop free
            try:
                quotes_data = await asyncio.wait_for(
                    loop.run_in_executor(
                        _quote_executor, _fetch_bulk_quotes_sync, symbol_list
                    ),
                    timeout=10.0,  # 10s max per fetch attempt
                )
            except asyncio.TimeoutError:
                logger.warning("Bulk quote fetch timed out after 10s")
                quotes_data = {
                    sym: {
                        "ltp": 0.0, "change": 0.0, "change_percent": 0.0,
                        "volume": 0, "last_traded_time": datetime.now().isoformat(),
                        "live": False, "error": "Fetch timed out",
                    }
                    for sym in symbol_list
                }
            
            await websocket.send_json({
                "type": "quote_update",
                "data": quotes_data,
                "timestamp": datetime.now().isoformat(),
            })
            
            await asyncio.sleep(2)
    
    except WebSocketDisconnect:
        logger.info(f"Quote WebSocket disconnected for symbols: {symbol_list[:5]}")
    except Exception as e:
        logger.error(f"Quote WebSocket error: {e}", exc_info=True)
        try:
            await websocket.close()
        except Exception:
            pass
