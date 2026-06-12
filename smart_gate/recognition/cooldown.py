"""Per-user cooldown helper for gate-open rate limiting.

A single instance tracks the last `touch()` time per user_id and answers
`passed(user_id)` based on a configurable window. Used by the detector to
suppress repeated CheckInEvents while a user stays in frame.

Not thread-safe — current callers (detector frame loop, bus consumer) run
from a single thread per channel. If that changes, wrap the dict in a Lock.
"""
from __future__ import annotations

import time


class UserCooldown:
    def __init__(self, window_s: float):
        self._window_s = window_s
        self._last: dict[int, float] = {}

    def passed(self, user_id: int) -> bool:
        last = self._last.get(user_id)
        if last is None:
            return True
        return (time.monotonic() - last) >= self._window_s

    def touch(self, user_id: int) -> None:
        self._last[user_id] = time.monotonic()
