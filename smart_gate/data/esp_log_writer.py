"""Batched writer thread for ESP log rows.

Coalesces ESP-emitted log lines (up to 20 Hz from the sensor task) into
periodic INSERTs. Reduces SD-card write amplification dramatically.
"""
from __future__ import annotations
import logging
import threading
from collections import deque
from typing import Tuple

log = logging.getLogger(__name__)

Row = Tuple[str, str, str]   # (level, tag, msg)


class EspLogWriter:
    def __init__(self, db, flush_interval_s: float = 1.0,
                 batch_max: int = 50, max_queue: int = 10_000):
        self._db = db
        self._flush_interval_s = flush_interval_s
        self._batch_max = batch_max
        self._q: deque[Row] = deque(maxlen=max_queue)
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="esp-log-writer")
        self._thread.start()

    def stop(self, timeout: float = 2.0):
        self._stop.set()
        with self._cond:
            self._cond.notify_all()
        if self._thread:
            self._thread.join(timeout=timeout)
            self._thread = None

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def enqueue(self, row: Row):
        with self._cond:
            self._q.append(row)   # deque(maxlen=max_queue) drops oldest
            self._cond.notify()

    def qsize(self) -> int:
        with self._lock:
            return len(self._q)

    def _loop(self):
        while not self._stop.is_set():
            batch: list[Row] = []
            with self._cond:
                if not self._q:
                    self._cond.wait(timeout=self._flush_interval_s)
                while self._q and len(batch) < self._batch_max:
                    batch.append(self._q.popleft())
            if not batch:
                continue
            try:
                self._db.insert_esp_log_many(batch)
            except Exception:
                log.exception("esp_log_writer: flush failed; %d rows lost",
                              len(batch))
