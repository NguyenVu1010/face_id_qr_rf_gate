"""In-process pub/sub for ESP32 log events.

Single publisher (smart_gate.main._handle_esp_event), N subscribers (one per
open SSE connection). Each subscriber gets its own bounded deque; overflow
drops the OLDEST entry so a slow consumer never blocks the publisher and
the bus-consumer thread never blocks on the bus.
"""
from __future__ import annotations

import collections
import threading


class EspLogBus:
    """Pub/sub with bounded per-subscriber queues."""

    def __init__(self, queue_cap: int = 200) -> None:
        self._queue_cap = queue_cap
        self._subscribers: list[collections.deque] = []
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)

    def subscribe(self) -> collections.deque:
        q: collections.deque = collections.deque(maxlen=self._queue_cap)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: collections.deque) -> None:
        with self._lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def publish(self, item: dict) -> None:
        with self._cond:
            for q in self._subscribers:
                q.append(item)         # deque(maxlen=N) drops oldest if full
            self._cond.notify_all()

    def wait_for_item(self, q: collections.deque,
                      timeout: float = 1.0) -> dict | None:
        with self._cond:
            if q:
                return q.popleft()
            self._cond.wait(timeout=timeout)
            return q.popleft() if q else None

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)
