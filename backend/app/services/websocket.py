"""
WebSocket Server for Real-Time Updates
"""

import logging
import asyncio
import json
from typing import Set, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"✅ WebSocket connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        self.active_connections.discard(websocket)
        logger.info(f"❌ WebSocket disconnected. Remaining: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: Dict[Any, Any], websocket: WebSocket):
        """Send message to specific client"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: Dict[Any, Any]):
        """Broadcast message to all connected clients"""
        disconnected = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to client: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)


# Global connection manager
manager = ConnectionManager()


# ============================
# BROADCAST HELPERS
# ============================

async def broadcast_mtm_update(data: Dict[str, Any]):
    """Broadcast MTM (Mark-to-Market) update"""
    await manager.broadcast({
        "type": "mtm_update",
        "data": data
    })


async def broadcast_position_update(data: Dict[str, Any]):
    """Broadcast position update"""
    await manager.broadcast({
        "type": "position_update",
        "data": data
    })


async def broadcast_trade_execution(data: Dict[str, Any]):
    """Broadcast trade execution"""
    await manager.broadcast({
        "type": "trade_execution",
        "data": data
    })


async def broadcast_notification(data: Dict[str, Any]):
    """Broadcast new notification"""
    await manager.broadcast({
        "type": "notification",
        "data": data
    })


async def broadcast_system_status(data: Dict[str, Any]):
    """Broadcast system status change"""
    await manager.broadcast({
        "type": "system_status",
        "data": data
    })


async def broadcast_daily_pnl(data: Dict[str, Any]):
    """Broadcast daily P&L update"""
    await manager.broadcast({
        "type": "daily_pnl",
        "data": data
    })


# ============================
# BACKGROUND TASKS
# ============================

async def periodic_mtm_updates(db: Session):
    """Send periodic MTM updates (every 5 seconds)"""
    while True:
        try:
            if manager.get_connection_count() > 0:
                # Get latest MTM data
                from app.core.execution.paper_mtm import update_paper_mtm
                
                update_paper_mtm(db)
                
                # Fetch updated positions
                from app.db.models_intent import ExecutionIntent
                
                positions = db.query(ExecutionIntent).filter(
                    ExecutionIntent.status == "EXECUTED"
                ).all()
                
                mtm_data = {
                    "positions": [
                        {
                            "intent_id": p.intent_id,
                            "strategy": p.strategy,
                            "underlying": p.underlying,
                            "pnl": p.pnl,
                            "last_updated": p.last_mtm_at.isoformat() if p.last_mtm_at else None
                        }
                        for p in positions
                    ],
                    "timestamp": asyncio.get_event_loop().time()
                }
                
                await broadcast_mtm_update(mtm_data)
            
            await asyncio.sleep(5)  # Update every 5 seconds
            
        except Exception as e:
            logger.error(f"Error in periodic MTM updates: {e}", exc_info=True)
            await asyncio.sleep(5)


async def periodic_system_health(db: Session):
    """Send periodic system health updates (every 10 seconds)"""
    while True:
        try:
            if manager.get_connection_count() > 0:
                from app.db.models_control import SystemControl
                
                system = db.query(SystemControl).first()
                
                health_data = {
                    "trading_enabled": system.trading_enabled if system else False,
                    "connected_clients": manager.get_connection_count(),
                    "timestamp": asyncio.get_event_loop().time()
                }
                
                await broadcast_system_status(health_data)
            
            await asyncio.sleep(10)  # Update every 10 seconds
            
        except Exception as e:
            logger.error(f"Error in system health updates: {e}", exc_info=True)
            await asyncio.sleep(10)
