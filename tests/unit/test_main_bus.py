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


# ---------------------------------------------------------------------------
# 1-of-3 _handle_checkin routing — face/qr send cmd:open, rfid does NOT.
# ---------------------------------------------------------------------------


def _checkin_fixtures():
    """Build a default fixture set for _handle_checkin tests. The matcher's
    user_name() returns 'alice' for any known user (any id != 999)."""
    db = MagicMock()
    db.insert_event.return_value = 7
    matcher = MagicMock()
    matcher.user_name = MagicMock(side_effect=lambda uid:
                                  "alice" if uid != 999 else f"id={uid}")
    uart = MagicMock()
    uart.send_cmd.return_value = {"ok": True}
    trig_queue = queue.Queue(maxsize=5)
    cfg = MagicMock()
    last_grant: dict = {}
    reload_event = threading.Event()
    esp_log_bus = MagicMock()
    return db, matcher, uart, trig_queue, cfg, last_grant, reload_event, esp_log_bus


def test_handle_checkin_face_method_writes_event_and_sends_cmd_open():
    """method=face → db.insert_event(method='face', granted=True)
    AND uart.send_cmd('open', ...)."""
    from smart_gate import main as main_mod
    from smart_gate.recognition.detector import CheckInEvent

    (db, matcher, uart, trig_queue, cfg,
     last_grant, reload_event, esp_log_bus) = _checkin_fixtures()
    evt = CheckInEvent(method="face", user_id=42, face_distance=0.18)

    main_mod._handle_checkin(evt, db, matcher, uart, trig_queue, cfg,
                             last_grant, reload_event, esp_log_bus)

    db.insert_event.assert_called_once()
    args, kwargs = db.insert_event.call_args
    # Signature is positional: (method, user_id, granted, detail=...)
    assert (kwargs.get("method", args[0] if args else None)) == "face"
    granted = kwargs.get("granted",
                         args[2] if len(args) > 2 else None)
    assert granted is True
    uart.send_cmd.assert_called_once()
    cmd_args, cmd_kwargs = uart.send_cmd.call_args
    assert cmd_args[0] == "open"


def test_handle_checkin_rfid_method_does_not_send_cmd_open():
    """ESP already opened the gate — Pi must not duplicate."""
    from smart_gate import main as main_mod
    from smart_gate.recognition.detector import CheckInEvent

    (db, matcher, uart, trig_queue, cfg,
     last_grant, reload_event, esp_log_bus) = _checkin_fixtures()
    evt = CheckInEvent(method="rfid", user_id=42, raw_uid="A1B2C3D4")

    main_mod._handle_checkin(evt, db, matcher, uart, trig_queue, cfg,
                             last_grant, reload_event, esp_log_bus)

    db.insert_event.assert_called_once()
    args, _ = db.insert_event.call_args
    assert args[0] == "rfid"
    uart.send_cmd.assert_not_called()


def test_handle_checkin_qr_method_sends_cmd_open():
    """method=qr → Pi sends cmd:open (ESP doesn't know about QR)."""
    from smart_gate import main as main_mod
    from smart_gate.recognition.detector import CheckInEvent

    (db, matcher, uart, trig_queue, cfg,
     last_grant, reload_event, esp_log_bus) = _checkin_fixtures()
    evt = CheckInEvent(method="qr", user_id=42, qr_token="TOKEN-XYZ")

    main_mod._handle_checkin(evt, db, matcher, uart, trig_queue, cfg,
                             last_grant, reload_event, esp_log_bus)

    db.insert_event.assert_called_once()
    uart.send_cmd.assert_called_once()
    cmd_args, _ = uart.send_cmd.call_args
    assert cmd_args[0] == "open"


def test_handle_checkin_unknown_user_does_not_write_event():
    """matcher.user_name returns 'id=<uid>' for unknowns → bail out."""
    from smart_gate import main as main_mod
    from smart_gate.recognition.detector import CheckInEvent

    (db, matcher, uart, trig_queue, cfg,
     last_grant, reload_event, esp_log_bus) = _checkin_fixtures()
    evt = CheckInEvent(method="face", user_id=999, face_distance=0.18)

    main_mod._handle_checkin(evt, db, matcher, uart, trig_queue, cfg,
                             last_grant, reload_event, esp_log_bus)

    db.insert_event.assert_not_called()
    uart.send_cmd.assert_not_called()
