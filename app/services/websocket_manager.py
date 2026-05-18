"""
WebSocket connection manager — handles live pipeline monitoring connections.

Manages per-request_id connection pools for real-time step updates.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections grouped by request_id.

    Pipeline steps call `broadcast()` to push real-time status updates
    to all connected clients watching a specific request.
    """

    def __init__(self) -> None:
        # Maps request_id -> list of active WebSocket connections
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, request_id: str, websocket: WebSocket) -> None:
        """Accept and register a WebSocket connection for a request."""
        await websocket.accept()
        if request_id not in self._connections:
            self._connections[request_id] = []
        self._connections[request_id].append(websocket)
        logger.info(f"WS connected: {request_id} (total: {len(self._connections[request_id])})")

    def disconnect(self, request_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if request_id in self._connections:
            self._connections[request_id] = [
                ws for ws in self._connections[request_id] if ws is not websocket
            ]
            if not self._connections[request_id]:
                del self._connections[request_id]
            logger.info(f"WS disconnected: {request_id}")

    async def broadcast(self, request_id: str, data: dict[str, Any]) -> None:
        """Send a JSON message to all connections watching a request_id."""
        if request_id not in self._connections:
            return

        message = json.dumps(data, default=str)
        dead_connections = []

        for websocket in self._connections[request_id]:
            try:
                await websocket.send_text(message)
            except Exception:
                dead_connections.append(websocket)

        # Clean up dead connections
        for ws in dead_connections:
            self.disconnect(request_id, ws)

    async def close_all(self, request_id: str) -> None:
        """Close all connections for a request (pipeline complete/failed)."""
        if request_id not in self._connections:
            return

        for websocket in self._connections[request_id]:
            try:
                await websocket.close()
            except Exception:
                pass

        del self._connections[request_id]
        logger.info(f"WS closed all: {request_id}")

    @property
    def active_connections(self) -> int:
        """Total number of active WebSocket connections."""
        return sum(len(conns) for conns in self._connections.values())


# Singleton instance used across the application
ws_manager = ConnectionManager()
