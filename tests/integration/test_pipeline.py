"""End-to-end style tests with mocked serial + camera."""
import os
import queue
import signal
import threading
import time
import numpy as np
import pytest

import smart_gate.link.uart_client as uart_mod
import smart_gate.video.capture as cap_mod
import smart_gate.recognition.detector as det_mod
import smart_gate.main as main_mod
from tests.integration.mocks.serial import FakeSerial, SerialException
from tests.integration.mocks.camera import FakeCV2Module


@pytest.fixture
def patched(monkeypatch, tmp_path):
    fakes = []
    def factory(port, baud, timeout=1.0):
        s = FakeSerial(port, baud, timeout)
        fakes.append(s)
        return s
    monkeypatch.setattr(uart_mod, "_open_serial", factory)
    monkeypatch.setattr(uart_mod, "SerialException", SerialException)

    fake_cv2 = FakeCV2Module(frames=[np.zeros((480, 640, 3), dtype=np.uint8)])
    original_run_capture = cap_mod.run_capture
    monkeypatch.setattr(cap_mod, "run_capture",
                        lambda *a, **kw: original_run_capture(*a, cv2_module=fake_cv2, **kw))

    monkeypatch.setattr(det_mod, "run_detector",
                        lambda *a, **kw: None)

    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(f"""
[paths]
data_dir = "{tmp_path / 'data'}"
log_dir = "{tmp_path / 'log'}"

[link]
port = "/dev/fake"
baud = 115200
ping_interval_s = 999
heartbeat_timeout_s = 30

[web]
host = "127.0.0.1"
port = 0
""")
    return cfg_file, fakes


def _trigger_shutdown():
    """Cooperative shutdown (signals don't fire in non-main pytest thread)."""
    if main_mod._current_shutdown is not None:
        main_mod._current_shutdown.set()
    else:
        os.kill(os.getpid(), signal.SIGTERM)


def test_boot_then_manual_open(patched, monkeypatch):
    cfg_file, fakes = patched
    def stub_web(*a, **kw):
        a[5].wait()
    monkeypatch.setattr(main_mod, "_run_web", stub_web)

    t = threading.Thread(target=main_mod.main, args=(["--config", str(cfg_file)],),
                         daemon=True)
    t.start()
    deadline = time.monotonic() + 3.0
    while not fakes and time.monotonic() < deadline:
        time.sleep(0.02)
    assert fakes, "FakeSerial never opened"
    fakes[-1].inject(b'{"type":"evt","v":"boot","data":{}}')
    time.sleep(0.2)
    _trigger_shutdown()
    t.join(timeout=10)
    assert not t.is_alive()


def test_uart_link_down_and_reconnect(patched, monkeypatch):
    cfg_file, fakes = patched
    def stub_web(*a, **kw):
        a[5].wait()
    monkeypatch.setattr(main_mod, "_run_web", stub_web)
    t = threading.Thread(target=main_mod.main, args=(["--config", str(cfg_file)],),
                         daemon=True)
    t.start()
    deadline = time.monotonic() + 3.0
    while not fakes and time.monotonic() < deadline:
        time.sleep(0.02)
    fakes[0].fail_next_read = True
    # reconnect loop in uart_client retries after 1s; wait long enough.
    deadline = time.monotonic() + 4.0
    while len(fakes) < 2 and time.monotonic() < deadline:
        time.sleep(0.05)
    assert len(fakes) >= 2
    _trigger_shutdown()
    t.join(timeout=10)
