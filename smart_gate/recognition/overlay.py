"""Shared face-detection overlay state.

Detector thread writes the latest bbox + match label here; the Flask
MJPEG generator reads it on each frame and draws an annotated overlay.
Stale entries (older than `stale_after_s`) are ignored so old bboxes
don't persist after the face leaves the frame.
"""
from __future__ import annotations

import dataclasses
import threading
import time


@dataclasses.dataclass(frozen=True)
class OverlayInfo:
    bbox: tuple[int, int, int, int] | None   # (x, y, w, h) pixel coords on BGR
    label: str | None                        # e.g. "demo (0.42)" or "stranger"
    color: tuple[int, int, int]              # BGR — green match, red stranger
    ts_mono: float


_EMPTY = OverlayInfo(bbox=None, label=None, color=(0, 255, 0), ts_mono=0.0)


class OverlayState:
    def __init__(self, stale_after_s: float = 2.0):
        self._lock = threading.Lock()
        self._info: OverlayInfo = _EMPTY
        self._stale_after_s = stale_after_s

    def set(self, bbox, label, color=(0, 255, 0)) -> None:
        with self._lock:
            self._info = OverlayInfo(
                bbox=bbox, label=label, color=color,
                ts_mono=time.monotonic(),
            )

    def clear(self) -> None:
        with self._lock:
            self._info = _EMPTY

    def get_if_fresh(self) -> OverlayInfo | None:
        with self._lock:
            info = self._info
        if info.bbox is None:
            return None
        if time.monotonic() - info.ts_mono > self._stale_after_s:
            return None
        return info
