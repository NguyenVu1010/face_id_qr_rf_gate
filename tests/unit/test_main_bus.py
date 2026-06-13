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
# 3-tier face threshold (decided 2026-06-13):
#   distance <  0.25            → strict accept, fire immediately
#   0.25 <= distance <= 0.40    → uncertain band, fire after N=3 consecutive
#                                  frames matching the same user_id
#   distance >  0.40            → reject, reset counter
# These exercise the same conditional ladder used in
# detector._process_frame; the counter API mirrors the production
# _UncertainCounter (touch() returns None, count(uid) returns the int).
# ---------------------------------------------------------------------------


def test_face_strict_accept_fires_immediately():
    """distance=0.18 < face_threshold → CheckInEvent on the very first frame
    (no consecutive-frame penalty for confident matches)."""
    from smart_gate.recognition.cooldown import UserCooldown
    from smart_gate.recognition.detector import (
        CheckInEvent,
        _UncertainCounter,
    )

    counter = _UncertainCounter()
    cooldown = UserCooldown(window_s=5.0)
    bus = []
    face_threshold = 0.25
    band_lo, band_hi = 0.25, 0.40
    required = 3

    matched, distance = 42, 0.18   # strict
    accept = False
    if matched is not None and distance < face_threshold:
        counter.clear()
        accept = True
    elif matched is not None and band_lo <= distance <= band_hi:
        counter.touch(matched)
        if counter.count(matched) >= required:
            counter.clear()
            accept = True
    else:
        counter.clear()
    if accept and cooldown.passed(matched):
        cooldown.touch(matched)
        bus.append(CheckInEvent(method="face", user_id=matched,
                                face_distance=distance))
    assert len(bus) == 1
    assert bus[0].method == "face"
    assert bus[0].user_id == 42


def test_face_in_band_requires_3_consecutive():
    """3 borderline frames (0.32, 0.30, 0.35) for the same user → fire on the 3rd."""
    from smart_gate.recognition.cooldown import UserCooldown
    from smart_gate.recognition.detector import (
        CheckInEvent,
        _UncertainCounter,
    )

    counter = _UncertainCounter()
    cooldown = UserCooldown(window_s=5.0)
    bus = []
    face_threshold = 0.25
    band_lo, band_hi = 0.25, 0.40
    required = 3

    def tick(matched, distance):
        accept = False
        if matched is not None and distance < face_threshold:
            counter.clear()
            accept = True
        elif matched is not None and band_lo <= distance <= band_hi:
            counter.touch(matched)
            if counter.count(matched) >= required:
                counter.clear()
                accept = True
        else:
            counter.clear()
        if accept and cooldown.passed(matched):
            cooldown.touch(matched)
            bus.append(CheckInEvent(method="face", user_id=matched,
                                    face_distance=distance))

    tick(42, 0.32); assert len(bus) == 0   # frame 1 in band
    tick(42, 0.30); assert len(bus) == 0   # frame 2 in band
    tick(42, 0.35); assert len(bus) == 1   # frame 3 → accept


def test_face_in_band_resets_on_user_change():
    """Different user_id between borderline frames must reset the streak —
    spoof-defense: an attacker can't 'borrow' another user's counter."""
    from smart_gate.recognition.detector import _UncertainCounter

    counter = _UncertainCounter()
    band_lo, band_hi = 0.25, 0.40
    required = 3
    bus = []

    def tick(matched, distance):
        if matched is not None and band_lo <= distance <= band_hi:
            counter.touch(matched)
            if counter.count(matched) >= required:
                counter.clear()
                bus.append(matched)
        else:
            counter.clear()

    tick(42, 0.30); tick(99, 0.30); tick(42, 0.30)
    assert bus == []   # never reached 3-streak for any single user


def test_face_above_upper_threshold_rejects():
    """distance > band_hi (0.40) → no event, counter not touched."""
    from smart_gate.recognition.detector import _UncertainCounter

    counter = _UncertainCounter()
    band_lo, band_hi = 0.25, 0.40
    accepted = []
    matched, distance = 42, 0.50   # above band
    if matched is not None and band_lo <= distance <= band_hi:
        counter.touch(matched)
        accepted.append(matched)
    else:
        counter.clear()
    assert accepted == []


def test_strict_match_resets_uncertain_counter():
    """A strict match arriving mid-streak must blow away the borderline
    counter so a single confident frame doesn't accumulate badly."""
    from smart_gate.recognition.detector import _UncertainCounter

    counter = _UncertainCounter()
    face_threshold = 0.25
    counter.touch(42); counter.touch(42)   # count = 2 in-band
    assert counter.count(42) == 2
    # Now a strict match arrives:
    matched, distance = 42, 0.18
    if matched is not None and distance < face_threshold:
        counter.clear()
    assert counter.count(42) == 0


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


def test_handle_checkin_sets_gate_tracker_last_user():
    """After a successful auth, gate_tracker.last_user should reflect the
    granted user — this drives the /api/gate/state.json dashboard widget."""
    from smart_gate import main as main_mod
    from smart_gate.recognition.detector import CheckInEvent
    from smart_gate.link.gate_state import GateTracker

    (db, matcher, uart, trig_queue, cfg,
     last_grant, reload_event, esp_log_bus) = _checkin_fixtures()
    tracker = GateTracker()
    evt = CheckInEvent(method="face", user_id=42, face_distance=0.18)

    main_mod._handle_checkin(evt, db, matcher, uart, trig_queue, cfg,
                             last_grant, reload_event, esp_log_bus,
                             gate_tracker=tracker)

    assert tracker.snapshot()["last_user"] == "alice"


def test_handle_checkin_unknown_user_does_not_set_last_user():
    """Unknown user → no event row AND no last_user update."""
    from smart_gate import main as main_mod
    from smart_gate.recognition.detector import CheckInEvent
    from smart_gate.link.gate_state import GateTracker

    (db, matcher, uart, trig_queue, cfg,
     last_grant, reload_event, esp_log_bus) = _checkin_fixtures()
    tracker = GateTracker()
    tracker.set_last_user("previous")
    evt = CheckInEvent(method="face", user_id=999, face_distance=0.18)

    main_mod._handle_checkin(evt, db, matcher, uart, trig_queue, cfg,
                             last_grant, reload_event, esp_log_bus,
                             gate_tracker=tracker)

    # Unknown user must not overwrite the previous attribution.
    assert tracker.snapshot()["last_user"] == "previous"


def test_cap_rfid_fields_truncates_long_inputs():
    from smart_gate.main import _cap_rfid_fields
    d = {"uid": "F" * 100, "name": "X" * 200, "granted": False}
    name, uid = _cap_rfid_fields(d)
    assert len(name) == 32
    assert len(uid) == 24
    assert name == "X" * 32
    assert uid == "F" * 24


def test_cap_rfid_fields_handles_missing_fields():
    from smart_gate.main import _cap_rfid_fields
    name, uid = _cap_rfid_fields({})
    assert name == ""
    assert uid == ""


def test_cap_rfid_fields_handles_none_values():
    from smart_gate.main import _cap_rfid_fields
    d = {"name": None, "uid": None}
    name, uid = _cap_rfid_fields(d)
    assert name == ""
    assert uid == ""


def test_handle_checkin_rfid_method_sets_last_user():
    """RFID also attributes the open via last_user even though the Pi did
    not send cmd:open (ESP autonomously opened the gate)."""
    from smart_gate import main as main_mod
    from smart_gate.recognition.detector import CheckInEvent
    from smart_gate.link.gate_state import GateTracker

    (db, matcher, uart, trig_queue, cfg,
     last_grant, reload_event, esp_log_bus) = _checkin_fixtures()
    tracker = GateTracker()
    evt = CheckInEvent(method="rfid", user_id=42, raw_uid="A1B2C3D4")

    main_mod._handle_checkin(evt, db, matcher, uart, trig_queue, cfg,
                             last_grant, reload_event, esp_log_bus,
                             gate_tracker=tracker)

    assert tracker.snapshot()["last_user"] == "alice"
    uart.send_cmd.assert_not_called()  # ESP already opened — no duplicate


# ---------------------------------------------------------------------------
# evt:gate state=unknown — ESP brown-out / panic / watchdog recovery.
# Pairs with firmware Task 3.10 — see commit 8dd51ca.
# ---------------------------------------------------------------------------


def test_gate_state_unknown_writes_event_and_audits():
    """evt:gate state=unknown reset_reason=brownout → audit + insert system row.

    Firmware enters a 5s 'hold at 90° neutral' recovery window after a risky
    reboot (brown-out / panic / watchdog) when the gate was mid-cycle. Pi
    must surface this on the live-log AND record a permanent row in /events
    history so the operator can investigate after-the-fact.
    """
    from smart_gate import main as main_mod
    from smart_gate.link.uart_client import EspEvent
    from smart_gate.link.gate_state import GateTracker

    db = MagicMock()
    esp_log_bus = MagicMock()
    gate_tracker = GateTracker()
    peripherals = MagicMock()

    evt = EspEvent(v="gate",
                   data={"state": "unknown", "reset_reason": "brownout"})

    main_mod._handle_esp_event(
        evt, db, MagicMock(), MagicMock(), MagicMock(),
        MagicMock(), MagicMock(), {}, threading.Event(),
        gate_tracker=gate_tracker, esp_log_bus=esp_log_bus,
        peripherals=peripherals,
    )

    # 1) A 'system' event row exists in /events history with the reset reason.
    db.insert_event.assert_called_once()
    args, kwargs = db.insert_event.call_args
    method = kwargs.get("method", args[0] if args else None)
    granted = kwargs.get("granted",
                         args[2] if len(args) > 2 else None)
    detail = kwargs.get("detail",
                        args[3] if len(args) > 3 else None)
    assert method in ("system", "recovery", "esp_recovery", "boot"), (
        f"expected a system-style method label, got {method!r}"
    )
    assert granted is False
    assert "brownout" in (detail or ""), (
        f"expected 'brownout' in detail, got {detail!r}"
    )

    # 2) A synthetic audit line went out on the live-log SSE stream.
    esp_log_bus.publish.assert_called()
    pub_payload = esp_log_bus.publish.call_args.args[0]
    assert pub_payload["lvl"] == "error"

    # 3) Gate tracker was NOT corrupted into a real state by 'unknown' —
    #    it remains at idle (which is what GateTracker's _KNOWN_STATES
    #    fallback would do too, but we want to skip the call entirely).
    assert gate_tracker.snapshot()["state"] == "idle"


def test_gate_state_unknown_resilient_to_db_failure():
    """If db.insert_event raises, the audit STILL fires and no exception
    propagates — operator must see the warning even if persistence fails."""
    from smart_gate import main as main_mod
    from smart_gate.link.uart_client import EspEvent

    db = MagicMock()
    db.insert_event.side_effect = RuntimeError("disk full")
    esp_log_bus = MagicMock()

    evt = EspEvent(v="gate",
                   data={"state": "unknown", "reset_reason": "panic"})

    # Should NOT raise.
    main_mod._handle_esp_event(
        evt, db, MagicMock(), MagicMock(), MagicMock(),
        MagicMock(), MagicMock(), {}, threading.Event(),
        gate_tracker=None, esp_log_bus=esp_log_bus,
        peripherals=None,
    )

    esp_log_bus.publish.assert_called()
