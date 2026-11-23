"""Optimizer notifications survive broadcaster teardown and multiple servers."""

import asyncio
import contextlib
import json
import queue
import threading

from v_ase.websocket_manager import WebSocketManager


class BoundSocket:
    def __init__(self, count=1):
        self.loop = asyncio.get_running_loop()
        self.messages = []
        self.complete = threading.Event()
        self.count = count

    async def accept(self):
        pass

    async def send_text(self, message):
        assert asyncio.get_running_loop() is self.loop
        self.messages.append(json.loads(message))
        if len(self.messages) >= self.count:
            self.complete.set()


def test_cancelled_broadcaster_cannot_steal_the_next_completion():
    class ObservedQueue(queue.Queue):
        def __init__(self):
            super().__init__()
            self.blocking_read = threading.Event()
            self.consumed = threading.Event()

        def get(self, block=True, timeout=None):
            if block:
                self.blocking_read.set()
                result = super().get(block=True, timeout=1)
                self.consumed.set()
                return result
            return super().get(block=False)

    async def scenario():
        manager = WebSocketManager()
        old_queue = ObservedQueue()
        manager.message_queue = old_queue
        retired = asyncio.create_task(manager.broadcaster_task())
        await asyncio.sleep(0.02)
        retired.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await retired
        current = asyncio.create_task(manager.broadcaster_task())
        await asyncio.sleep(0.01)
        socket = BoundSocket()
        await manager.connect(socket, 'next-document')
        try:
            manager.broadcast_sync({'type': 'registry_relax_finished'}, session_id='next-document')
            for _ in range(50):
                if socket.complete.is_set():
                    break
                await asyncio.sleep(0.01)
            assert socket.messages == [{'type': 'registry_relax_finished'}], {
                'retired_reader_consumed_event': old_queue.consumed.is_set(),
                'blocking_reader_started': old_queue.blocking_read.is_set(),
            }
        finally:
            manager.disconnect(socket)
            current.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await current

    asyncio.run(scenario())


def test_multiple_server_loops_deliver_ordered_notifications_on_their_own_loop():
    manager = WebSocketManager()
    ready = [threading.Event(), threading.Event()]
    stop = threading.Event()
    sockets = [None, None]
    failures = []

    def serve(index):
        async def scenario():
            socket = BoundSocket(count=21)
            sockets[index] = socket
            task = asyncio.create_task(manager.broadcaster_task())
            await asyncio.sleep(0)
            await manager.connect(socket, f'workspace:document-{index}')
            ready[index].set()
            try:
                while not stop.is_set():
                    await asyncio.sleep(0.01)
            finally:
                manager.disconnect(socket)
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        try:
            asyncio.run(scenario())
        except BaseException as error:
            failures.append(error)

    threads = [threading.Thread(target=serve, args=(index,), daemon=True) for index in range(2)]
    try:
        for thread in threads:
            thread.start()
        assert all(event.wait(2) for event in ready)
        for step in range(20):
            manager.broadcast_sync({'step': step})
        manager.broadcast_sync({'target': 0}, session_id='workspace:document-0')
        manager.broadcast_sync({'target': 1}, session_prefix='workspace:document-1')
        assert all(socket.complete.wait(2) for socket in sockets)
        for index, socket in enumerate(sockets):
            assert socket.messages == [{'step': step} for step in range(20)] + [{'target': index}]
    finally:
        stop.set()
        for thread in threads:
            thread.join(timeout=2)
    assert not failures
    assert not manager.active_connections
    assert not any(thread.is_alive() for thread in threads)
