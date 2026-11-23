import asyncio
import json
import threading
import queue
from typing import Any, Dict, Optional

try:
    from fastapi import WebSocket
except ModuleNotFoundError:
    WebSocket = Any

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[WebSocket, Optional[str]] = {}
        self._connection_loops = {}
        self._loop_queues = {}
        self._loop_broadcasters = {}
        self._lock = threading.RLock()
        self._stop_broadcaster = threading.Event()

    async def connect(self, websocket: WebSocket, session_id: Optional[str] = None):
        await websocket.accept()
        loop = asyncio.get_running_loop()
        with self._lock:
            self.active_connections[websocket] = session_id
            self._connection_loops[websocket] = loop
            self._loop_queues.setdefault(loop, queue.Queue())

    def disconnect(self, websocket: WebSocket):
        with self._lock:
            self.active_connections.pop(websocket, None)
            self._connection_loops.pop(websocket, None)

    def _connections(self):
        with self._lock:
            return list(self.active_connections.items())

    def has_session_connection(self, session_id: str) -> bool:
        return any(connection_session == session_id for _, connection_session in self._connections())

    def has_connection_prefix(self, session_prefix: str) -> bool:
        return any(
            isinstance(connection_session, str)
            and connection_session.startswith(session_prefix)
            for _, connection_session in self._connections()
        )

    def command_connection(self, *, session_id=None, session_prefix=None):
        """Choose one unambiguous command consumer; never broadcast mutations."""
        matches = [connection for connection, scope in self._connections()
                   if (session_id is None or scope == session_id)
                   and (session_prefix is None or isinstance(scope, str) and scope.startswith(session_prefix))]
        if not matches:
            raise ValueError("No live v_ase browser is connected. Open human_url and retry.")
        if len(matches) != 1:
            raise ValueError("Multiple live browsers are connected for this document/workspace. Close duplicate windows before issuing semantic commands.")
        return matches[0]

    def broadcast_sync(
        self,
        message: dict,
        session_id: Optional[str] = None,
        session_prefix: Optional[str] = None,
    ):
        """Thread-safe method to queue a message for broadcasting."""
        item = (session_id, session_prefix, json.dumps(message))
        # Each server owns its sockets on its own event loop. Fan out under one
        # lock so concurrent worker threads preserve the same order everywhere.
        with self._lock:
            for messages in self._loop_queues.values():
                messages.put_nowait(item)

    async def broadcaster_task(self):
        """Deliver ordered messages only to sockets owned by this server loop."""
        loop = asyncio.get_running_loop()
        with self._lock:
            messages = self._loop_queues.setdefault(loop, queue.Queue())
            self._loop_broadcasters[loop] = self._loop_broadcasters.get(loop, 0) + 1
        try:
            while not self._stop_broadcaster.is_set():
                try:
                    # Cancelling to_thread(queue.get) leaves its worker alive:
                    # it can steal a later document's completion notification.
                    # A nonblocking read has no reader outliving this task.
                    session_id, session_prefix, msg = messages.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.01)
                    continue
                with self._lock:
                    connections = [(connection, scope) for connection, scope in self.active_connections.items()
                                   if self._connection_loops.get(connection) is loop]
                try:
                    for connection, connection_session in connections:
                        if session_id is not None and connection_session != session_id:
                            continue
                        if (
                            session_prefix is not None
                            and (
                                not isinstance(connection_session, str)
                                or not connection_session.startswith(session_prefix)
                            )
                        ):
                            continue
                        try:
                            await connection.send_text(msg)
                        except Exception:
                            # Dead connection will be handled by disconnect.
                            pass
                finally:
                    messages.task_done()
        finally:
            with self._lock:
                remaining = self._loop_broadcasters[loop] - 1
                if remaining:
                    self._loop_broadcasters[loop] = remaining
                else:
                    self._loop_broadcasters.pop(loop, None)
                    self._loop_queues.pop(loop, None)

    def stop(self):
        self._stop_broadcaster.set()

# Shared routing, with independent delivery queues for each server event loop.
ws_manager = WebSocketManager()
