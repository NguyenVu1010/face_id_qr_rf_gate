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
        self._cond = threading.Condition()
        self._state: str = "idle"
        self._since_mono: float = time.monotonic()
        self._last_user: str | None = None

    def update(self, state: str, user: str | None = None) -> str | None:
        """Set state; returns the PREVIOUS state if it changed, else None.
        Notifies any waiters in wait_for_state()."""
        state = state.lower()
        if state not in _KNOWN_STATES:
            state = "idle"
        with self._cond:
            prev = self._state
            if prev == state:
                return None
            self._state = state
            self._since_mono = time.monotonic()
            if user is not None:
                self._last_user = user
            self._cond.notify_all()
        return prev

    def set_last_user(self, user: str) -> None:
        """Record the most recent authorized user without changing state.

        Used by _handle_checkin to attribute the latest open to a name even
        when the gate state hasn't changed yet (e.g., RFID where ESP opens
        autonomously and the Pi only mirrors the state via evt:gate).
        """
        with self._cond:
            self._last_user = user
            # No state change → no notify (waiters only care about state).

    def wait_for_state(self, target: str, timeout: float = 3.0) -> bool:
        """Block up to `timeout` seconds for the gate to enter `target` state.
        Returns True if reached (or already in target), False on timeout.
        Used by web _gate_action to confirm ESP32 actually moved the servo
        after a cmd:open / cmd:close, not just acked the JSON."""
        deadline = time.monotonic() + timeout
        target = target.lower()
        with self._cond:
            while self._state != target:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._cond.wait(timeout=remaining)
            return True

    def snapshot(self) -> dict:
        with self._cond:
            return {
                "state": self._state,
                "since_s": round(time.monotonic() - self._since_mono, 2),
                "last_user": self._last_user,
            }
