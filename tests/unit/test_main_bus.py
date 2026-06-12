"""Tests for the bus-consumer thread in smart_gate.main.

The consumer is a long-lived module-level function. Unhandled exceptions
from a handler (DB write failure, schema drift, etc.) must NOT kill the
thread — it must log, emit a synthetic audit line, back off briefly, and
keep processing subsequent events.
"""
from __future__ import annotations

import queue
import threading
import time
from unittest.mock import MagicMock

from smart_gate.recognition.detector import AuthEvent
from smart_gate import main as main_mod


def test_bus_consumer_survives_handler_exception(monkeypatch):
    """If a handler raises, the consumer logs + audits and keeps going."""
    bus: queue.Queue = queue.Queue()
    shutdown = threading.Event()
    reload_event = threading.Event()

    db = MagicMock()
    matcher = MagicMock()
    uart = MagicMock()
    trig_queue: queue.Queue = queue.Queue()
    cfg = MagicMock()
    esp_log_bus = MagicMock()

    # First handler invocation raises, second succeeds.
    call_count = {"n": 0}

    def fake_handler(evt, db_, uart_, trig_, esp_log_bus_=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("disk full")
        # second call: succeed silently

    monkeypatch.setattr(main_mod, "_handle_manual_event", fake_handler)

    t = threading.Thread(
        target=main_mod._consume_bus,
        args=(bus, db, matcher, uart, trig_queue, cfg, shutdown, reload_event),
        kwargs={"esp_log_bus": esp_log_bus},
        daemon=True,
    )
    t.start()

    evt1 = AuthEvent(method="manual_open", user_id=None, granted=True)
    evt2 = AuthEvent(method="manual_open", user_id=None, granted=True)

    bus.put(evt1)
    # Wait long enough for the 0.5 s back-off to elapse, then submit evt2.
    time.sleep(0.8)
    bus.put(evt2)
    time.sleep(0.3)

    shutdown.set()
    t.join(timeout=3)

    assert not t.is_alive(), "bus consumer thread leaked"
    assert call_count["n"] == 2, (
        f"second event was not processed after handler raised "
        f"(call_count={call_count['n']})"
    )
    # A synthetic audit line should have been published on the failure.
    assert esp_log_bus.publish.called, (
        "expected synthetic audit publish() on handler failure"
    )


# ---------------------------------------------------------------------------
# 1-of-3 detector branch logic (harness-style; does NOT spin up the camera).
# ---------------------------------------------------------------------------


def test_face_match_below_threshold_fires_checkin_event_with_cooldown():
    """Direct unit-test of the face-branch logic — synthesize the conditional
    used in detector.run loop, not the loop itself (camera is hard to fake)."""
    from smart_gate.recognition.cooldown import UserCooldown
    from smart_gate.recognition.detector import CheckInEvent

    cooldown = UserCooldown(window_s=5.0)
    bus = []
    face_threshold = 0.25

    matched_user_id = 42
    distance = 0.18
    if matched_user_id is not None and distance < face_threshold:
        if cooldown.passed(matched_user_id):
            cooldown.touch(matched_user_id)
            bus.append(CheckInEvent(method="face", user_id=42,
                                    face_distance=distance))
    assert len(bus) == 1
    assert bus[0].method == "face"
    assert bus[0].user_id == 42
    assert bus[0].face_distance == 0.18


def test_face_match_above_threshold_does_not_fire():
    from smart_gate.recognition.cooldown import UserCooldown
    from smart_gate.recognition.detector import CheckInEvent
    cooldown = UserCooldown(window_s=5.0)
    bus = []
    face_threshold = 0.25
    matched_user_id = 42
    distance = 0.30   # above threshold
    if matched_user_id is not None and distance < face_threshold:
        if cooldown.passed(matched_user_id):
            cooldown.touch(matched_user_id)
            bus.append(CheckInEvent(method="face", user_id=42,
                                    face_distance=distance))
    assert bus == []


def test_checkin_event_method_qr_with_no_face_distance():
    from smart_gate.recognition.detector import CheckInEvent
    e = CheckInEvent(method="qr", user_id=7)
    assert e.method == "qr"
    assert e.face_distance is None
