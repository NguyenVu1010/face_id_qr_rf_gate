"""Mock serial.Serial for tests. No real hardware involved."""
from __future__ import annotations

import queue
import threading
import time


class SerialException(Exception):
    pass


class FakeSerial:
    """Behaviour:
    - write(b): appends to self.written (captured) and pushes ack lines if scripted.
    - readline(): pops a line from self._rx_queue or blocks up to timeout.
    - inject(line): test code pushes a line that readline() will return.
    - fail_next_write/fail_next_read: trigger SerialException.
    """
    def __init__(self, port, baud, timeout=1.0):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.written: list[bytes] = []
        self._rx_queue: queue.Queue[bytes] = queue.Queue()
        self._lock = threading.Lock()
        self._closed = False
        self.fail_next_write = False
        self.fail_next_read = False

    def write(self, data: bytes) -> int:
        if self._closed:
            raise SerialException("closed")
        if self.fail_next_write:
            self.fail_next_write = False
            raise SerialException("scripted write failure")
        with self._lock:
            self.written.append(data)
        return len(data)

    def readline(self) -> bytes:
        if self._closed:
            raise SerialException("closed")
        # Poll for fail_next_read / closed even while waiting so tests can
        # trigger failures without waiting for the full timeout to elapse.
        deadline = time.monotonic() + self.timeout if self.timeout is not None else None
        while True:
            if self._closed:
                raise SerialException("closed")
            if self.fail_next_read:
                self.fail_next_read = False
                raise SerialException("scripted read failure")
            try:
                return self._rx_queue.get(timeout=0.05)
            except queue.Empty:
                if deadline is not None and time.monotonic() >= deadline:
                    return b""

    def inject(self, line: bytes) -> None:
        if not line.endswith(b"\n"):
            line = line + b"\n"
        self._rx_queue.put(line)

    def close(self) -> None:
        self._closed = True

    @property
    def is_open(self) -> bool:
        return not self._closed
