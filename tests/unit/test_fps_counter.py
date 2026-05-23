import time
import pytest
from smart_gate.video.fps_counter import FpsCounter


def test_empty_counter_reports_zero():
    fc = FpsCounter(window_s=1.0)
    assert fc.fps() == 0.0


def test_fps_is_count_over_window(monkeypatch):
    fc = FpsCounter(window_s=2.0)
    t = [1000.0]
    monkeypatch.setattr("time.monotonic", lambda: t[0])
    # 6 ticks within window
    for _ in range(6):
        fc.tick()
    # 6 events / 2.0s window = 3.0 fps
    assert fc.fps() == 3.0


def test_stale_ticks_are_evicted(monkeypatch):
    fc = FpsCounter(window_s=1.0)
    t = [1000.0]
    monkeypatch.setattr("time.monotonic", lambda: t[0])
    fc.tick(); fc.tick(); fc.tick()
    assert fc.fps() == 3.0
    t[0] = 1002.0   # advance past window
    # All three ticks now older than 1.0s
    assert fc.fps() == 0.0


def test_thread_safe_burst():
    import threading
    fc = FpsCounter(window_s=5.0)
    def burst():
        for _ in range(1000):
            fc.tick()
    threads = [threading.Thread(target=burst) for _ in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    # 4 × 1000 ticks within a 5s window → 800 fps
    assert fc.fps() == pytest.approx(800.0, abs=1.0)
