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


def _new(name: str) -> PeripheralState:
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
        """ESP32 evt:log → update tagged peripheral state."""
        if not tag or tag not in self._states:
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
        """Pi received an ack from a cmd. Servo + LCD must be alive for
        gate cmds to ack cleanly, so we treat a successful open/close ack
        as evidence both are OK."""
        ts = _now_iso()
        with self._lock:
            link = self._states["link"]
            self._states["link"] = PeripheralState(
                name="link",
                status="ok" if ok else "warning",
                last_message=f"ack {verb}: {detail}" if detail else f"ack {verb}",
                last_ts=ts,
                last_ts_mono=time.monotonic(),
            )
            self._link_last_alive_mono = time.monotonic()
            if verb in ("open", "close") and ok:
                for name in ("servo", "lcd"):
                    self._states[name] = PeripheralState(
                        name=name, status="ok",
                        last_message=f"acknowledged via cmd:{verb}",
                        last_ts=ts, last_ts_mono=time.monotonic(),
                    )

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
