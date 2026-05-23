"""Rolling-window FPS counter.

Counts events within the last `window_s` seconds. Thread-safe. Used by
capture and detector to expose FPS to /healthz.
"""
from __future__ import annotations

import collections
import threading
import time


class FpsCounter:
    def __init__(self, window_s: float = 5.0) -> None:
        self._window_s = window_s
        self._timestamps: collections.deque = collections.deque()
        self._lock = threading.Lock()

    def tick(self) -> None:
        now = time.monotonic()
        with self._lock:
            self._timestamps.append(now)
            cutoff = now - self._window_s
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()

    def fps(self) -> float:
        now = time.monotonic()
        with self._lock:
            cutoff = now - self._window_s
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            if not self._timestamps:
                return 0.0
            return len(self._timestamps) / self._window_s
