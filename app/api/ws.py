"""
WebSocket endpoint — live pipeline monitoring.

Clients connect to /ws/pipeline/{request_id} to receive real-time
step status updates during enrichment execution.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/pipeline/{request_id}")
async def pipeline_ws(websocket: WebSocket, request_id: str):
    """WebSocket endpoint for live pipeline monitoring.

    Clients receive JSON messages with step status updates:
    {
        "step": "fetch_apis",
        "status": "started",
        "timestamp": "2024-01-01T00:00:00Z"
    }

    The connection stays open until the pipeline completes or fails,
    or the client disconnects.
    """
    await ws_manager.connect(request_id, websocket)
    try:
        # Keep connection alive — wait for client messages or disconnect
        while True:
            # We only receive pings/keepalives from the client
            data = await websocket.receive_text()
            # Echo back as acknowledgment
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(request_id, websocket)
        logger.info(f"WS client disconnected: {request_id}")
    except Exception as e:
        ws_manager.disconnect(request_id, websocket)
        logger.warning(f"WS error for {request_id}: {e}")
