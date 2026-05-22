import threading
import time
from smart_gate.video.recorder import RingBuffer


def test_ring_push_and_snapshot():
    ring = RingBuffer(fps=15, pre_seconds=2)         # capacity 30
    for i in range(5):
        ring.push(f"jpg{i}".encode(), time.monotonic())
    snap = ring.snapshot()
    assert [item[1] for item in snap] == [b"jpg0", b"jpg1", b"jpg2", b"jpg3", b"jpg4"]


def test_ring_evicts_oldest_when_full():
    ring = RingBuffer(fps=15, pre_seconds=1)         # capacity 15
    for i in range(20):
        ring.push(f"jpg{i}".encode(), time.monotonic())
    snap = ring.snapshot()
    assert len(snap) == 15
    assert snap[0][1] == b"jpg5"
    assert snap[-1][1] == b"jpg19"


def test_ring_thread_safe_concurrent_push():
    ring = RingBuffer(fps=15, pre_seconds=4)         # cap 60
    errors = []
    def writer():
        try:
            for i in range(100):
                ring.push(f"j{i}".encode(), time.monotonic())
        except Exception as e:
            errors.append(e)
    threads = [threading.Thread(target=writer) for _ in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert errors == []
    snap = ring.snapshot()
    assert len(snap) == 60                            # bounded
