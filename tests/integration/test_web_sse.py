import json
import threading
import time
from unittest.mock import MagicMock
import pytest
from smart_gate.data.db import Database
from smart_gate.link.esp_log_bus import EspLogBus
from smart_gate.web.app import create_app


PLACEHOLDER = b"\xff\xd8\xff\xd9"


@pytest.fixture
def sse_setup(tmp_data_dir):
    db = Database(tmp_data_dir / "sse.db"); db.migrate()
    hub = MagicMock(); hub.wait_jpeg.return_value = PLACEHOLDER
    uart = MagicMock(); uart.link_alive.return_value = True
    bus = EspLogBus()
    app = create_app(db=db, hub=hub, uart=uart, data_dir=tmp_data_dir,
                     esp_log_bus=bus)
    return app, db, bus


def _read_until(iterator, marker: bytes, timeout: float = 1.0) -> bytes:
    deadline = time.monotonic() + timeout
    buf = b""
    for chunk in iterator:
        buf += chunk
        if marker in buf:
            return buf
        if time.monotonic() > deadline:
            break
    return buf


def test_sse_endpoint_serves_event_stream(sse_setup):
    app, _db, bus = sse_setup
    with app.test_client() as c:
        # buffered=False keeps the body lazy
        resp = c.get("/api/esp_log/stream", buffered=False)
        assert resp.status_code == 200
        assert resp.headers["Content-Type"].startswith("text/event-stream")

        # Publish from another thread
        def pub():
            time.sleep(0.05)
            bus.publish({"id": 1, "ts": "2026-05-23T14:02:09",
                         "lvl": "info", "tag": "rfid", "msg": "hi"})
        threading.Thread(target=pub, daemon=True).start()

        buf = _read_until(resp.response, b"event: log", timeout=1.5)
        assert b"event: log" in buf
        assert b"id: 1" in buf
        assert b"\"msg\":\"hi\"" in buf or b'"msg": "hi"' in buf
        resp.close()


def test_sse_replays_via_last_event_id(sse_setup):
    app, db, _bus = sse_setup
    db.insert_esp_log("info", "a", "first")
    db.insert_esp_log("info", "b", "second")
    third = db.insert_esp_log("info", "c", "third")
    with app.test_client() as c:
        resp = c.get("/api/esp_log/stream",
                     headers={"Last-Event-ID": "1"},
                     buffered=False)
        buf = _read_until(resp.response, b"third", timeout=1.0)
        assert b"second" in buf
        assert b"third" in buf
        resp.close()


def test_sse_unsubscribes_on_disconnect(sse_setup):
    app, _db, bus = sse_setup
    with app.test_client() as c:
        resp = c.get("/api/esp_log/stream", buffered=False)
        # Read one initial chunk so the generator subscribes
        next(resp.response, None)
        time.sleep(0.05)
        assert bus.subscriber_count() >= 1
        resp.close()
        # Give the generator a moment to finalize
        for _ in range(20):
            if bus.subscriber_count() == 0:
                break
            time.sleep(0.05)
        assert bus.subscriber_count() == 0


def test_api_esp_log_fragment_returns_html(sse_setup):
    app, db, _bus = sse_setup
    db.insert_esp_log("warn", "audio", "missing peripheral")
    with app.test_client() as c:
        r = c.get("/api/esp_log?limit=10")
        assert r.status_code == 200
        assert b"missing peripheral" in r.data
        # HTML by default, no JSON braces
        assert not r.data.lstrip().startswith(b"[")
