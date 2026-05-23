"""Track per-peripheral health on the Pi side from ESP32 evt:log + ack signals.

The Pi cannot directly probe the ESP32 peripherals (RC522, LCD, HC-SR04,
servo, buzzer). It must infer state from:
- ESP32 evt:log messages tagged by peripheral name
- cmd:open / cmd:close ack outcomes (servo + LCD respond when cmd succeeds)
- The link itself being alive (heartbeat)

State transitions:
- ok       → recent successful operation (info log) or ack
- warning  → recent warn-level log
- missing  → err-level log, or no echo / init failed pattern
- unknown  → never heard from since boot

Each peripheral records the most recent message + timestamp so the
dashboard can show "what went wrong" alongside the colour.
"""
from __future__ import annotations

import dataclasses
import threading
import time


# Peripherals the firmware tags messages with. New peripherals only need
# to be added here + the firmware needs to emit evt:log with the matching
# tag for the tracker to follow.
KNOWN_PERIPHERALS = ("rfid", "lcd", "sensor", "servo", "buzzer", "link")

_MISSING_PATTERNS = (
    "no echo",         # HC-SR04 trig pulse but no echo back
    "init failed",     # firmware init
    "not detected",
    "missing",
    "absent",
    "no ack",
    "timeout",
    "not responding",
)


@dataclasses.dataclass
class PeripheralState:
    name: str
    status: str            # ok | warning | missing | unknown
    last_message: str
    last_ts: str           # ISO-ish, server-side wall clock
    last_ts_mono: float    # internal monotonic for age computation


# Peripherals without any feedback path back to the ESP32 — there is no
# way to verify they are physically connected or working short of adding
# extra sensing hardware (current sensor / microphone / scope). These
# stay in status="na" forever; the dashboard renders them with a neutral
# label "no feedback available".
NO_FEEDBACK_PERIPHERALS = ("servo", "buzzer")

_NA_MESSAGE = (
    "no feedback wire — verify by physical observation only "
    "(SG90/buzzer don't report back to MCU)"
)


def _new(name: str) -> PeripheralState:
    if name in NO_FEEDBACK_PERIPHERALS:
        return PeripheralState(name=name, status="na",
                               last_message=_NA_MESSAGE,
                               last_ts="", last_ts_mono=0.0)
    return PeripheralState(name=name, status="unknown",
                           last_message="", last_ts="", last_ts_mono=0.0)


class PeripheralTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._states: dict[str, PeripheralState] = {
            name: _new(name) for name in KNOWN_PERIPHERALS
        }
        # Seed link as unknown until first heartbeat or ack
        self._link_last_alive_mono: float = 0.0

    # --- writers ---

    def update_from_log(self, lvl: str, tag: str | None,
                        msg: str, ts: str | None = None) -> None:
        """ESP32 evt:log → update tagged peripheral state.

        Skips peripherals in NO_FEEDBACK_PERIPHERALS — those have no
        observability path so any 'info' log about them would be
        firmware-side guessing, not real verification.
        """
        if not tag or tag not in self._states:
            return
        if tag in NO_FEEDBACK_PERIPHERALS:
            return
        lvl = (lvl or "info").lower()
        text = (msg or "").lower()
        # Classify
        if lvl in ("err", "error", "fatal"):
            status = "missing"
        elif any(p in text for p in _MISSING_PATTERNS):
            status = "missing"
        elif lvl in ("warn", "warning"):
            status = "warning"
        else:
            status = "ok"
        with self._lock:
            self._states[tag] = PeripheralState(
                name=tag, status=status,
                last_message=msg or "", last_ts=ts or _now_iso(),
                last_ts_mono=time.monotonic(),
            )

    def mark_cmd_ack(self, verb: str, ok: bool, detail: str = "") -> None:
        """Pi received an ack from a cmd. This proves only that the UART
        link is alive and ESP32 parsed the JSON — it does NOT prove the
        servo physically moved or the LCD displayed anything. Only the
        `link` peripheral is marked ok here. Servo/LCD/etc require
        evidence from evt:gate state transitions or evt:log entries.
        """
        ts = _now_iso()
        with self._lock:
            self._states["link"] = PeripheralState(
                name="link",
                status="ok" if ok else "warning",
                last_message=f"ack {verb}: {detail}" if detail else f"ack {verb}",
                last_ts=ts,
                last_ts_mono=time.monotonic(),
            )
            self._link_last_alive_mono = time.monotonic()

    def mark_gate_state(self, state: str) -> None:
        """evt:gate transition — no-op for SG90 because we can't actually
        verify the servo moved (no feedback wire). The gate state badge
        on the dashboard already shows transitions; duplicating that
        into 'servo: ok' here would be misleading.

        Kept as a hook so future hardware (ACS712 current sense) can fill
        in real verification without changing callers.
        """
        return

    def mark_cmd_failed(self, verb: str, error: str) -> None:
        with self._lock:
            self._states["link"] = PeripheralState(
                name="link", status="missing",
                last_message=f"cmd:{verb} failed: {error}",
                last_ts=_now_iso(), last_ts_mono=time.monotonic(),
            )

    def mark_heartbeat(self) -> None:
        with self._lock:
            self._link_last_alive_mono = time.monotonic()
            cur = self._states["link"]
            # Only promote to ok if currently unknown — preserve missing/warn
            # that came from a specific err log until next info confirms.
            if cur.status in ("unknown",):
                self._states["link"] = PeripheralState(
                    name="link", status="ok",
                    last_message="heartbeat received",
                    last_ts=_now_iso(), last_ts_mono=time.monotonic(),
                )

    def mark_rfid_scan(self, granted: bool, name_seen: str | None) -> None:
        """An evt:rfid arrived — RFID hardware is alive regardless of grant."""
        with self._lock:
            self._states["rfid"] = PeripheralState(
                name="rfid", status="ok",
                last_message=f"scan: {'granted' if granted else 'denied'} "
                             f"name={name_seen or '?'}",
                last_ts=_now_iso(), last_ts_mono=time.monotonic(),
            )

    # --- readers ---

    def snapshot(self) -> list[dict]:
        now_mono = time.monotonic()
        with self._lock:
            out = []
            for name in KNOWN_PERIPHERALS:
                s = self._states[name]
                age = (now_mono - s.last_ts_mono) if s.last_ts_mono else None
                out.append({
                    "name": s.name,
                    "status": s.status,
                    "last_message": s.last_message,
                    "last_ts": s.last_ts,
                    "age_s": round(age, 1) if age is not None else None,
                })
            return out


def _now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")
