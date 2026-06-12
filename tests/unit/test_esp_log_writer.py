import time
import pytest
from unittest.mock import MagicMock


def test_writer_batches_rows_within_flush_window():
    from smart_gate.data.esp_log_writer import EspLogWriter
    db = MagicMock()
    w = EspLogWriter(db, flush_interval_s=0.1, batch_max=10)
    w.start()
    try:
        for i in range(5):
            w.enqueue(("info", "test", f"msg{i}"))
        time.sleep(0.3)
    finally:
        w.stop()
    assert db.insert_esp_log_many.call_count >= 1
    rows = db.insert_esp_log_many.call_args[0][0]
    assert len(rows) == 5


def test_writer_drops_oldest_when_queue_full():
    from smart_gate.data.esp_log_writer import EspLogWriter
    db = MagicMock()
    w = EspLogWriter(db, flush_interval_s=10.0, batch_max=10, max_queue=3)
    for i in range(5):
        w.enqueue(("info", "t", f"m{i}"))
    assert w.qsize() == 3


def test_writer_swallows_db_exceptions():
    from smart_gate.data.esp_log_writer import EspLogWriter
    db = MagicMock()
    db.insert_esp_log_many.side_effect = RuntimeError("boom")
    w = EspLogWriter(db, flush_interval_s=0.05)
    w.start()
    try:
        w.enqueue(("warn", "tag", "msg"))
        time.sleep(0.2)
        # Writer thread must still be alive after the failing flush.
        assert w.is_alive()
    finally:
        w.stop()
