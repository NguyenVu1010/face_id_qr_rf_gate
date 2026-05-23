"""Track the gate's runtime state as reported by ESP32 evt:gate messages.

The ESP32 owns the authoritative state machine (architecture spec §4.5):
    idle → opening → open → (closing|timeout_warn → closing) → closed → idle

Pi mirrors it here so the dashboard can render a status badge and the
events log can record timeouts. The state is purely informational on
the Pi side — Pi does not drive the FSM, it just listens.
"""
from __future__ import annotations

import threading
import time

_KNOWN_STATES = (
    "idle", "opening", "open", "timeout_warn", "closing", "closed",
)


class GateTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._state: str = "idle"
        self._since_mono: float = time.monotonic()
        self._last_user: str | None = None

    def update(self, state: str, user: str | None = None) -> str | None:
        """Set state; returns the PREVIOUS state if it changed, else None."""
        state = state.lower()
        if state not in _KNOWN_STATES:
            state = "idle"
        with self._lock:
            prev = self._state
            if prev == state:
                return None
            self._state = state
            self._since_mono = time.monotonic()
            if user is not None:
                self._last_user = user
        return prev

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "state": self._state,
                "since_s": round(time.monotonic() - self._since_mono, 2),
                "last_user": self._last_user,
            }
