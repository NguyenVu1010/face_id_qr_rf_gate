"""3-tier face-threshold tests for the detector branch logic.

Decision 2026-06-13:
    distance <  face_threshold              → fire immediately
    face_threshold <= distance <= band_hi   → fire after N consecutive
                                              frames matching the same uid
    distance >  band_hi                     → reject, clear band tracker

These tests synthesize the same conditional ladder used inside
`detector._process_frame` (the camera loop is too heavy to spin up
in unit tests). They share style with test_main_bus.py's
test_face_match_below_threshold_fires_checkin_event_with_cooldown.
"""
from __future__ import annotations

import pytest

from smart_gate.recognition.cooldown import UserCooldown
from smart_gate.recognition.detector import (
    CheckInEvent,
    _UncertainCounter,
    _uncertain_counter,
)


FACE_THRESHOLD = 0.25
BAND_LO = 0.25
BAND_HI = 0.40
REQUIRED_CONSEC = 3


def _decide(uid, distance, *, counter, bus, cooldown=None,
            face_threshold=FACE_THRESHOLD,
            band_lo=BAND_LO, band_hi=BAND_HI,
            required_consec=REQUIRED_CONSEC):
    """Mirror of the production conditional ladder in detector._process_frame.
    Mutates `bus` (list) and `counter`. Returns nothing.
    """
    if uid is not None and distance < face_threshold:
        counter.clear()
        if cooldown is None or cooldown.passed(uid):
            if cooldown is not None:
                cooldown.touch(uid)
            bus.append(CheckInEvent(method="face", user_id=uid,
                                    face_distance=float(distance)))
    elif uid is not None and band_lo <= distance <= band_hi:
        counter.touch(uid)
        if counter.count(uid) >= required_consec:
            counter.clear()
            if cooldown is None or cooldown.passed(uid):
                if cooldown is not None:
                    cooldown.touch(uid)
                bus.append(CheckInEvent(method="face", user_id=uid,
                                        face_distance=float(distance)))
    else:
        counter.clear()


@pytest.fixture
def counter():
    """Fresh counter per test — uses the local _UncertainCounter class so
    tests do not bleed state through the module-level singleton."""
    return _UncertainCounter()


# ---------------------------------------------------------------------------
# Tier 1: strict accept
# ---------------------------------------------------------------------------


def test_face_under_strict_threshold_fires_immediately(counter):
    """distance < face_threshold → CheckInEvent, no consecutive needed."""
    bus = []
    _decide(uid=42, distance=0.18, counter=counter, bus=bus)
    assert len(bus) == 1
    assert bus[0].method == "face"
    assert bus[0].user_id == 42
    assert bus[0].face_distance == pytest.approx(0.18)


def test_strict_match_resets_uncertain_counter(counter):
    """user_a at 0.30 (count=1), then user_a at 0.18 (strict) → CheckInEvent
    fires AND counter reset (so subsequent borderline restarts from 1)."""
    bus = []
    _decide(uid=42, distance=0.30, counter=counter, bus=bus)
    assert bus == []                       # still building consec
    assert counter.count(42) == 1
    _decide(uid=42, distance=0.18, counter=counter, bus=bus)
    assert len(bus) == 1                   # strict fired
    assert counter.count(42) == 0          # cleared
    # And a follow-up borderline frame starts at 1, not 2.
    _decide(uid=42, distance=0.30, counter=counter, bus=bus)
    assert counter.count(42) == 1


# ---------------------------------------------------------------------------
# Tier 2: uncertain band — N consecutive
# ---------------------------------------------------------------------------


def test_face_in_uncertain_band_requires_3_consecutive(counter):
    """3 frames at distance=0.30 for same user_id → CheckInEvent on the 3rd."""
    bus = []
    _decide(uid=42, distance=0.30, counter=counter, bus=bus)
    assert bus == []
    assert counter.count(42) == 1
    _decide(uid=42, distance=0.30, counter=counter, bus=bus)
    assert bus == []
    assert counter.count(42) == 2
    _decide(uid=42, distance=0.30, counter=counter, bus=bus)
    assert len(bus) == 1
    assert bus[0].user_id == 42
    assert bus[0].face_distance == pytest.approx(0.30)
    # Counter cleared after fire so the 4th borderline frame restarts at 1.
    assert counter.count(42) == 0


def test_face_in_uncertain_band_at_boundaries_counts(counter):
    """band_lo and band_hi are inclusive — both should count toward consec."""
    bus = []
    _decide(uid=42, distance=BAND_LO, counter=counter, bus=bus)
    _decide(uid=42, distance=BAND_HI, counter=counter, bus=bus)
    _decide(uid=42, distance=0.30, counter=counter, bus=bus)
    assert len(bus) == 1


def test_face_in_uncertain_band_resets_on_user_change(counter):
    """user_a at 0.30, user_b at 0.30, user_a at 0.30 → no CheckInEvent —
    each user_id swap resets the consecutive counter to 1."""
    bus = []
    _decide(uid=1, distance=0.30, counter=counter, bus=bus)
    assert counter.count(1) == 1
    _decide(uid=2, distance=0.30, counter=counter, bus=bus)
    assert counter.count(2) == 1
    assert counter.count(1) == 0           # different last_uid
    _decide(uid=1, distance=0.30, counter=counter, bus=bus)
    assert counter.count(1) == 1
    assert bus == []                       # never reached 3 in a row


# ---------------------------------------------------------------------------
# Tier 3: reject
# ---------------------------------------------------------------------------


def test_face_above_upper_threshold_rejects(counter):
    """distance > band_hi → no event, counter cleared."""
    bus = []
    # Prime the counter first.
    _decide(uid=42, distance=0.30, counter=counter, bus=bus)
    _decide(uid=42, distance=0.30, counter=counter, bus=bus)
    assert counter.count(42) == 2
    _decide(uid=42, distance=0.50, counter=counter, bus=bus)
    assert bus == []
    assert counter.count(42) == 0          # blown away by reject


def test_no_match_clears_counter(counter):
    """uid is None (no candidate) → counter cleared even mid-borderline."""
    bus = []
    _decide(uid=42, distance=0.30, counter=counter, bus=bus)
    _decide(uid=42, distance=0.30, counter=counter, bus=bus)
    assert counter.count(42) == 2
    _decide(uid=None, distance=float("inf"), counter=counter, bus=bus)
    assert bus == []
    assert counter.count(42) == 0


# ---------------------------------------------------------------------------
# Cooldown still gates fires across both strict + borderline paths.
# ---------------------------------------------------------------------------


def test_cooldown_suppresses_strict_fire(counter):
    """Two strict matches inside the cooldown window → only the first fires."""
    bus = []
    cd = UserCooldown(window_s=5.0)
    _decide(uid=42, distance=0.18, counter=counter, bus=bus, cooldown=cd)
    _decide(uid=42, distance=0.18, counter=counter, bus=bus, cooldown=cd)
    assert len(bus) == 1


def test_cooldown_suppresses_borderline_fire(counter):
    """First borderline burst fires; second burst within cooldown window
    is suppressed even though it crossed N consecutive again."""
    bus = []
    cd = UserCooldown(window_s=5.0)
    for _ in range(3):
        _decide(uid=42, distance=0.30, counter=counter, bus=bus, cooldown=cd)
    assert len(bus) == 1
    # Counter is cleared on fire; build another 3 consec — still within cooldown.
    for _ in range(3):
        _decide(uid=42, distance=0.30, counter=counter, bus=bus, cooldown=cd)
    assert len(bus) == 1                   # cooldown blocked the second fire


# ---------------------------------------------------------------------------
# Module-level singleton sanity — production wires `_uncertain_counter` so
# verify it exposes the expected API and starts cleared on fresh import.
# ---------------------------------------------------------------------------


def test_module_singleton_exists_and_starts_cleared():
    """Belt-and-braces: the production detector module exports the singleton
    used in `_process_frame`. We do not depend on its current state (other
    tests may have touched it), only that the API is wired."""
    assert hasattr(_uncertain_counter, "touch")
    assert hasattr(_uncertain_counter, "count")
    assert hasattr(_uncertain_counter, "clear")
    _uncertain_counter.clear()
    assert _uncertain_counter.count(1) == 0
