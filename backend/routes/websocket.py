"""WebSocket manager for real-time updates."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, channel: str = "general"):
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = set()
        self.active_connections[channel].add(websocket)
        logger.info(f"WS connected to channel '{channel}' (total: {sum(len(v) for v in self.active_connections.values())})")
    
    def disconnect(self, websocket: WebSocket, channel: str = "general"):
        if channel in self.active_connections:
            self.active_connections[channel].discard(websocket)
    
    async def broadcast(self, message: dict, channel: str = "general"):
        if channel not in self.active_connections:
            return
        dead = set()
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message)
            except Exception:
                dead.add(connection)
        for d in dead:
            self.active_connections[channel].discard(d)
    
    async def broadcast_all(self, message: dict):
        for channel in self.active_connections:
            await self.broadcast(message, channel)

manager = ConnectionManager()

@router.websocket("/ws/{channel}")
async def websocket_endpoint(websocket: WebSocket, channel: str = "general"):
    await manager.connect(websocket, channel)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back or handle commands
            try:
                msg = json.loads(data)
                if msg.get('type') == 'ping':
                    await websocket.send_json({'type': 'pong'})
                else:
                    # Broadcast to channel
                    await manager.broadcast({'type': 'message', 'data': msg}, channel)
            except json.JSONDecodeError:
                await websocket.send_json({'type': 'error', 'message': 'Invalid JSON'})
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel)
        logger.info(f"WS disconnected from channel '{channel}'")

# Helper function for other modules to send real-time updates
async def notify(event_type: str, data: dict, channel: str = "general"):
    """Send a real-time notification to connected clients."""
    await manager.broadcast({'type': event_type, 'data': data}, channel)
