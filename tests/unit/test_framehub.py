import threading
import time
import pytest
from smart_gate.video.framehub import FrameHub


def test_publish_then_wait_returns_latest():
    hub = FrameHub()
    hub.publish(b"jpeg1", "bgr1")
    hub.publish(b"jpeg2", "bgr2")           # latest wins
    jpg = hub.wait_jpeg(timeout=1.0)
    assert jpg == b"jpeg2"
    bgr = hub.wait_bgr(timeout=1.0)
    assert bgr == "bgr2"


def test_wait_blocks_until_publish():
    hub = FrameHub()
    got = []
    def consumer():
        got.append(hub.wait_jpeg(timeout=2.0))
    t = threading.Thread(target=consumer)
    t.start()
    time.sleep(0.05)
    hub.publish(b"jpegX", "bgrX")
    t.join(timeout=2.0)
    assert got == [b"jpegX"]


def test_wait_timeout_returns_none():
    hub = FrameHub()
    assert hub.wait_jpeg(timeout=0.05) is None
    assert hub.wait_bgr(timeout=0.05) is None


def test_publish_none_wakes_consumers_with_none():
    hub = FrameHub()
    got = []
    def consumer():
        got.append(hub.wait_jpeg(timeout=2.0))
    t = threading.Thread(target=consumer)
    t.start()
    time.sleep(0.05)
    hub.publish(None, None)
    t.join(timeout=2.0)
    assert got == [None]
