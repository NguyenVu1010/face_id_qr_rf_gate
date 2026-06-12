import json
import threading
import time
import pytest
import queue
from smart_gate.link.uart_client import UartClient, LinkTimeout, LinkDown
from tests.integration.mocks.serial import FakeSerial


@pytest.fixture
def fake_serial(monkeypatch):
    fakes: list[FakeSerial] = []
    def factory(port, baud, timeout=1.0):
        s = FakeSerial(port, baud, timeout)
        fakes.append(s)
        return s
    import smart_gate.link.uart_client as mod
    monkeypatch.setattr(mod, "_open_serial", factory)
    monkeypatch.setattr(mod, "SerialException", __import__(
        "tests.integration.mocks.serial", fromlist=["SerialException"]
    ).SerialException)
    return fakes


@pytest.fixture
def event_bus():
    return queue.Queue()


def _start_client(fake_serial, event_bus):
    shutdown = threading.Event()
    client = UartClient("/dev/fake", 115200, event_bus, shutdown,
                        ping_interval_s=999)
    client.start()
    deadline = time.monotonic() + 2.0
    while not fake_serial and time.monotonic() < deadline:
        time.sleep(0.01)
    assert fake_serial, "FakeSerial never created"
    return client, shutdown


def test_connects_and_marks_alive(fake_serial, event_bus):
    client, shutdown = _start_client(fake_serial, event_bus)
    fake_serial[-1].inject(b'{"type":"evt","v":"boot","data":{}}')
    time.sleep(0.1)
    assert client.link_alive()
    shutdown.set()
    client.join(timeout=2.0)


def test_send_cmd_with_ack(fake_serial, event_bus):
    client, shutdown = _start_client(fake_serial, event_bus)
    ser = fake_serial[-1]
    def auto_ack():
        time.sleep(0.05)
        last = ser.written[-1] if ser.written else b""
        obj = json.loads(last.rstrip(b"\n"))
        ser.inject(json.dumps({"id": obj["id"], "type": "ack", "v": obj["v"],
                               "data": {"ok": True}}).encode())
    threading.Thread(target=auto_ack, daemon=True).start()
    data = client.send_cmd("open", {"user": "alice", "reason": "face"}, timeout=2.0)
    assert data == {"ok": True}
    shutdown.set()
    client.join(timeout=2.0)


def test_send_cmd_timeout(fake_serial, event_bus):
    client, shutdown = _start_client(fake_serial, event_bus)
    with pytest.raises(LinkTimeout):
        client.send_cmd("ping", timeout=0.2)
    shutdown.set()
    client.join(timeout=2.0)


def test_evt_log_pushed_to_event_bus(fake_serial, event_bus):
    client, shutdown = _start_client(fake_serial, event_bus)
    fake_serial[-1].inject(
        b'{"type":"evt","v":"log","data":{"lvl":"warn","tag":"x","msg":"hi"}}')
    time.sleep(0.1)
    items = []
    while not event_bus.empty():
        items.append(event_bus.get_nowait())
    assert any(getattr(i, "v", None) == "log" for i in items)
    shutdown.set()
    client.join(timeout=2.0)


def test_malformed_line_does_not_crash(fake_serial, event_bus):
    client, shutdown = _start_client(fake_serial, event_bus)
    fake_serial[-1].inject(b'{not json}')
    fake_serial[-1].inject(b'{"type":"evt","v":"heartbeat","data":{}}')
    time.sleep(0.1)
    assert client.link_alive()
    shutdown.set()
    client.join(timeout=2.0)


def test_reconnect_after_read_failure(fake_serial, event_bus):
    client, shutdown = _start_client(fake_serial, event_bus)
    ser = fake_serial[-1]
    ser.fail_next_read = True
    time.sleep(0.3)
    assert len(fake_serial) >= 2
    shutdown.set()
    client.join(timeout=2.0)


def test_tx_registers_pending_before_write(fake_serial, event_bus):
    """An ACK that arrives immediately after write() must find _pending
    already populated, otherwise _dispatch silently drops it and send_cmd
    blocks for the full timeout.

    ESP ACK round-trip is sub-millisecond at 115200 bps. To deterministically
    expose the race, the FakeSerial's write() injects the ACK BEFORE
    returning — so the rx thread can dispatch the ack while the tx thread is
    still inside ser.write(). If _pending is only registered AFTER write,
    the ack lookup fails and send_cmd raises LinkTimeout.
    """
    client, shutdown = _start_client(fake_serial, event_bus)
    ser = fake_serial[-1]

    # Monkeypatch the fake's write() so it injects the ack BEFORE returning.
    # This guarantees the rx thread sees the ack while tx is still in the
    # critical section, regardless of any post-write registration code.
    original_write = ser.write

    def write_then_inject(data: bytes) -> int:
        n = original_write(data)
        # Decode the just-written line to build a matching ack.
        try:
            obj = json.loads(data.rstrip(b"\n"))
        except Exception:
            return n
        ack = json.dumps({
            "id": obj["id"], "type": "ack", "v": obj["v"],
            "data": {"ok": True},
        }).encode()
        ser.inject(ack)
        # Give the rx thread a chance to dispatch the ack right now, while
        # we're still "inside" write() from the tx thread's perspective.
        time.sleep(0.05)
        return n

    ser.write = write_then_inject

    t0 = time.monotonic()
    data = client.send_cmd("open", {"user": "alice", "reason": "face"},
                           timeout=2.0)
    elapsed = time.monotonic() - t0

    assert data == {"ok": True}, (
        f"send_cmd returned {data!r}; ack was dropped due to "
        "register-after-write race"
    )
    assert elapsed < 1.5, (
        f"send_cmd took {elapsed:.2f}s — expected sub-second; this means "
        "the ack was dropped and we blocked on the full timeout"
    )

    shutdown.set()
    client.join(timeout=2.0)


def test_uart_client_next_id_seeded_from_time(monkeypatch):
    """The cmd id counter must start at int(time.time()) so it stays
    monotonic across Pi restarts within the same ESP boot session,
    not from 1 (which would be rejected as replay after the first
    Pi reboot).
    """
    import smart_gate.link.uart_client as mod
    monkeypatch.setattr(mod.time, "time", lambda: 1_700_000_000.0)
    # Bypass __init__ so we don't have to construct queues / events /
    # the whole serial machinery just to exercise the id seed.
    c = UartClient.__new__(UartClient)
    c._init_id_counter()
    assert next(c._next_id) == 1_700_000_000
    assert next(c._next_id) == 1_700_000_001


def test_rx_loop_discards_oversized_non_terminated_line(
    fake_serial, event_bus, caplog
):
    """A read_until that returns bytes WITHOUT a trailing \\n must be discarded,
    not parsed as a partial line and not accumulated.

    Simulates a floating ESP UART that streams non-\\n bytes at 115200 bps —
    pyserial's read_until() would return up to size= bytes without a newline.
    The rx loop must drop these and continue, not feed them into protocol.decode.
    """
    import logging as _logging
    from smart_gate.link import protocol

    # Attach our own handler to the uart_client logger so we capture warnings
    # emitted from the rx THREAD — pytest's caplog only sees records routed
    # through the root logger handler chain on the main thread, which is
    # unreliable for thread-based code.
    records: list[_logging.LogRecord] = []

    class _ListHandler(_logging.Handler):
        def emit(self, record):
            records.append(record)

    target_logger = _logging.getLogger("smart_gate.link.uart_client")
    handler = _ListHandler(level=_logging.WARNING)
    target_logger.addHandler(handler)
    try:
        client, shutdown = _start_client(fake_serial, event_bus)
        ser = fake_serial[-1]

        # Inject a chunk that is over MAX_LINE and has NO trailing \n. The fake's
        # inject_raw helper lets us bypass the auto-\n append used by inject().
        payload = b"A" * (protocol.MAX_LINE * 2)
        ser.inject_raw(payload)

        # Inject a well-formed event after the oversized garbage to prove the rx
        # loop keeps draining lines and is not stuck on the bad bytes.
        ser.inject(b'{"type":"evt","v":"heartbeat","data":{}}')

        # Give the rx loop time to read both injections.
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            if any("non-terminated" in r.getMessage() for r in records):
                break
            time.sleep(0.02)

        # Assertion 1: a warning log mentioning non-terminated bytes was emitted.
        msgs = [r.getMessage() for r in records]
        assert any("non-terminated" in m for m in msgs), (
            f"expected 'non-terminated' warning, got: {msgs}"
        )

        # Assertion 2: the well-formed heartbeat that followed was still parsed,
        # i.e. the link is alive (last_rx was updated by the heartbeat, not by
        # the discarded garbage).
        assert client.link_alive(), "rx loop should keep draining after discard"

        shutdown.set()
        client.join(timeout=2.0)
    finally:
        target_logger.removeHandler(handler)
