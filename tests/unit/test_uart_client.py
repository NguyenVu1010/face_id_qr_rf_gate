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
