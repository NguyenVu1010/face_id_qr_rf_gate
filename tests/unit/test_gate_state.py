"""Tests for GateTracker, especially wait_for_state used by the web layer
to confirm physical gate transitions after a cmd:open / cmd:close."""
import threading
import time

import pytest

from smart_gate.link.gate_state import GateTracker


def test_initial_state_idle():
    t = GateTracker()
    snap = t.snapshot()
    assert snap["state"] == "idle"


def test_update_returns_prev_on_change():
    t = GateTracker()
    assert t.update("opening") == "idle"
    assert t.update("open") == "opening"
    # No change → None
    assert t.update("open") is None


def test_unknown_state_clamped_to_idle():
    t = GateTracker()
    t.update("opening")
    assert t.update("garbage_state") == "opening"
    assert t.snapshot()["state"] == "idle"


def test_wait_for_state_already_there_returns_immediately():
    t = GateTracker()
    t.update("open")
    t0 = time.monotonic()
    assert t.wait_for_state("open", timeout=2.0) is True
    assert time.monotonic() - t0 < 0.05


def test_wait_for_state_timeout_returns_false():
    t = GateTracker()
    t0 = time.monotonic()
    assert t.wait_for_state("open", timeout=0.1) is False
    elapsed = time.monotonic() - t0
    assert 0.08 < elapsed < 0.3


def test_wait_for_state_notified_on_transition():
    t = GateTracker()
    result = {"got": None, "elapsed": None}

    def waiter():
        t0 = time.monotonic()
        result["got"] = t.wait_for_state("open", timeout=2.0)
        result["elapsed"] = time.monotonic() - t0

    th = threading.Thread(target=waiter)
    th.start()
    time.sleep(0.05)
    t.update("opening")        # not the target — shouldn't satisfy
    time.sleep(0.05)
    t.update("open")           # target reached
    th.join(timeout=1.0)
    assert result["got"] is True
    assert result["elapsed"] < 0.5


def test_wait_for_state_target_case_insensitive():
    t = GateTracker()
    t.update("open")
    assert t.wait_for_state("OPEN", timeout=0.5) is True


def test_set_last_user_does_not_change_state():
    from smart_gate.link.gate_state import GateTracker
    t = GateTracker()
    t.update("opening")
    t.set_last_user("alice")
    snap = t.snapshot()
    assert snap["state"] == "opening"
    assert snap["last_user"] == "alice"


def test_set_last_user_overrides_previous():
    from smart_gate.link.gate_state import GateTracker
    t = GateTracker()
    t.set_last_user("alice")
    t.set_last_user("bob")
    assert t.snapshot()["last_user"] == "bob"
