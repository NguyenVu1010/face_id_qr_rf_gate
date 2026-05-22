"""Latest-frame, multi-consumer fan-out hub.

cap thread is the sole publisher; multiple consumer threads block on
wait_jpeg()/wait_bgr() until the next publish. Each call returns the
most recent value, not a queued one — old frames are dropped.
"""
from __future__ import annotations

import threading


class FrameHub:
    def __init__(self):
        self._cond = threading.Condition()
        self._jpeg: bytes | None = None
        self._bgr = None
        self._seq = 0

    def publish(self, jpeg: bytes | None, bgr) -> None:
        with self._cond:
            self._jpeg = jpeg
            self._bgr = bgr
            self._seq += 1
            self._cond.notify_all()

    def _wait(self, attr: str, timeout: float | None):
        with self._cond:
            ok = self._cond.wait_for(lambda: self._seq > 0, timeout=timeout)
            if not ok:
                return None
            return getattr(self, attr)

    def wait_jpeg(self, timeout: float | None = None) -> bytes | None:
        return self._wait("_jpeg", timeout)

    def wait_bgr(self, timeout: float | None = None):
        return self._wait("_bgr", timeout)
