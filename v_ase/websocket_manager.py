import asyncio
import json
import threading
import queue
from typing import Any, Dict, List, Optional

try:
    from fastapi import WebSocket
except ModuleNotFoundError:
    WebSocket = Any

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[WebSocket, Optional[str]] = {}
        self.message_queue = queue.Queue()
        self._stop_broadcaster = threading.Event()

    async def connect(self, websocket: WebSocket, session_id: Optional[str] = None):
        await websocket.accept()
        self.active_connections[websocket] = session_id

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]

    def has_session_connection(self, session_id: str) -> bool:
        return any(connection_session == session_id for connection_session in self.active_connections.values())

    def broadcast_sync(self, message: dict, session_id: Optional[str] = None):
        """Thread-safe method to queue a message for broadcasting."""
        self.message_queue.put((session_id, json.dumps(message)))

    async def broadcaster_task(self):
        """Asynchronous task to consume the queue and send messages to all clients."""
        while not self._stop_broadcaster.is_set():
            try:
                # Use a small timeout to allow checking the stop event
                session_id, msg = await asyncio.to_thread(self.message_queue.get, timeout=0.1)
                for connection, connection_session in list(self.active_connections.items()):
                    if session_id is not None and connection_session != session_id:
                        continue
                    try:
                        await connection.send_text(msg)
                    except Exception:
                        # Dead connection will be handled by disconnect
                        pass
                self.message_queue.task_done()
            except queue.Empty:
                await asyncio.sleep(0.01)
            except RuntimeError as e:
                if "cannot schedule new futures after shutdown" in str(e):
                    break
                print(f"Broadcaster error: {e}")
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"Broadcaster error: {e}")
                await asyncio.sleep(0.1)

    def stop(self):
        self._stop_broadcaster.set()

# Global manager instance (simplified for demo, in production this would be per-session or app-wide)
ws_manager = WebSocketManager()
