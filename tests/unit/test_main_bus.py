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
