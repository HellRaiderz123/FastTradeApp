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
