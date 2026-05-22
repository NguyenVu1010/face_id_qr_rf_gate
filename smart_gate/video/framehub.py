"""Latest-frame, multi-consumer fan-out hub.

cap thread is the sole publisher; multiple consumer threads block on
wait_jpeg()/wait_bgr() until a new publish *for that channel* since the
consumer's last wake on that channel. Each (consumer thread, channel)
pair has its own last-seen seq tracked via threading.local.
"""
from __future__ import annotations

import threading


class FrameHub:
    def __init__(self):
        self._cond = threading.Condition()
        self._jpeg: bytes | None = None
        self._bgr = None
        self._seq = 0                  # incremented on every publish
        self._tls = threading.local()  # per-thread dict[channel_name -> last_seen_seq]

    def publish(self, jpeg: bytes | None, bgr) -> None:
        with self._cond:
            self._jpeg = jpeg
            self._bgr = bgr
            self._seq += 1
            self._cond.notify_all()

    def _last_seen(self, channel: str) -> int:
        seen_dict = getattr(self._tls, "seen", None)
        if seen_dict is None:
            seen_dict = {}
            self._tls.seen = seen_dict
        return seen_dict.get(channel, 0)

    def _set_seen(self, channel: str, seq: int) -> None:
        seen_dict = getattr(self._tls, "seen", None)
        if seen_dict is None:
            seen_dict = {}
            self._tls.seen = seen_dict
        seen_dict[channel] = seq

    def _wait(self, channel: str, attr: str, timeout: float | None):
        with self._cond:
            seen = self._last_seen(channel)
            if self._seq <= seen:
                ok = self._cond.wait_for(lambda: self._seq > seen, timeout=timeout)
                if not ok:
                    return None
            self._set_seen(channel, self._seq)
            return getattr(self, attr)

    def wait_jpeg(self, timeout: float | None = None) -> bytes | None:
        return self._wait("jpeg", "_jpeg", timeout)

    def wait_bgr(self, timeout: float | None = None):
        return self._wait("bgr", "_bgr", timeout)
