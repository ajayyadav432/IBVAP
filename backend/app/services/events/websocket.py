# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.events.websocket
# Description: Resilient WebSocket connection manager for real-time alert broadcasting.
# License: Apache-2.0
# ==============================================================================

import asyncio
import json
import threading
from typing import List, Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect

from app.core.logging import api_logger


class ConnectionManager:
    """
    Manages active WebSocket client connections for real-time event broadcasting.
    Resilient to client disconnections, connection errors, and multi-client scenarios.
    """

    def __init__(self):
        self._active_connections: List[WebSocket] = []
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """Set the asyncio event loop for thread-safe cross-thread dispatching."""
        self._loop = loop

    async def connect(self, websocket: WebSocket):
        """Accept and register a new client connection."""
        try:
            self._loop = asyncio.get_running_loop()
        except Exception:
            pass
        await websocket.accept()
        with self._lock:
            if websocket not in self._active_connections:
                self._active_connections.append(websocket)
        api_logger.info(f"WebSocket client connected. Total clients: {len(self._active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Unregister a client connection."""
        with self._lock:
            if websocket in self._active_connections:
                self._active_connections.remove(websocket)
        api_logger.info(f"WebSocket client disconnected. Remaining clients: {len(self._active_connections)}")

    async def broadcast_async(self, message: Dict[str, Any]):
        """Asynchronously broadcast JSON message to all connected clients."""
        with self._lock:
            connections = list(self._active_connections)

        if not connections:
            return

        payload_str = json.dumps(message)
        dead_connections = []

        for conn in connections:
            try:
                await conn.send_text(payload_str)
            except Exception as exc:
                api_logger.warning(f"Error sending WebSocket message to client: {exc}")
                dead_connections.append(conn)

        if dead_connections:
            with self._lock:
                for dead in dead_connections:
                    if dead in self._active_connections:
                        self._active_connections.remove(dead)

    def broadcast(self, message: Dict[str, Any]):
        """
        Thread-safe synchronous wrapper for broadcast.
        Safe to call from background worker threads or sync request handlers.
        """
        with self._lock:
            connections = list(self._active_connections)

        if not connections:
            return

        payload_str = json.dumps(message)
        dead_connections = []

        for conn in connections:
            sent = False
            # 1. Try loop dispatch if loop is running
            if self._loop is not None and not self._loop.is_closed() and self._loop.is_running():
                try:
                    fut = asyncio.run_coroutine_threadsafe(conn.send_text(payload_str), self._loop)
                    # wait shortly for completion
                    fut.result(timeout=1.0)
                    sent = True
                except Exception:
                    pass

            if not sent:
                # 2. Try anyio or active thread loop
                try:
                    import anyio.from_thread
                    anyio.from_thread.run(conn.send_text, payload_str)
                    sent = True
                except Exception:
                    pass

            if not sent:
                try:
                    cur_loop = None
                    try:
                        cur_loop = asyncio.get_running_loop()
                    except RuntimeError:
                        pass

                    if cur_loop is not None and cur_loop.is_running():
                        asyncio.create_task(conn.send_text(payload_str))
                        sent = True
                    else:
                        asyncio.run(conn.send_text(payload_str))
                        sent = True
                except Exception as exc:
                    api_logger.warning(f"Error sending WebSocket message: {exc}")
                    dead_connections.append(conn)

        if dead_connections:
            with self._lock:
                for dead in dead_connections:
                    if dead in self._active_connections:
                        self._active_connections.remove(dead)

    @property
    def client_count(self) -> int:
        """Return count of active connected clients."""
        with self._lock:
            return len(self._active_connections)


connection_manager = ConnectionManager()
