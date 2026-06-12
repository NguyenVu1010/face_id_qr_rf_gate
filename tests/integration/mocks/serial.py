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
    - read_until(term, size): pops a chunk; honours `size=` by truncating
      anything larger and returning the truncated prefix WITHOUT the
      terminator (mirroring real pyserial behaviour when the cap is hit
      before the terminator is seen).
    - inject(line): test code pushes a line (auto-appends \\n) for readline.
    - inject_raw(chunk): test code pushes a chunk verbatim — used to
      simulate floating UART garbage with no \\n.
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

    def _read_one(self) -> bytes:
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

    def readline(self) -> bytes:
        return self._read_one()

    def read_until(self, terminator: bytes = b"\n", size: int | None = None) -> bytes:
        """Pop one queued chunk. If size is set and the chunk exceeds it,
        return the first `size` bytes WITHOUT the terminator — matching
        pyserial's behaviour when the byte cap is hit before the terminator.
        If the chunk already contains the terminator within `size` bytes,
        return up to and including the terminator.
        """
        chunk = self._read_one()
        if size is not None and len(chunk) > size:
            return chunk[:size]
        return chunk

    def inject(self, line: bytes) -> None:
        if not line.endswith(b"\n"):
            line = line + b"\n"
        self._rx_queue.put(line)

    def inject_raw(self, chunk: bytes) -> None:
        """Push a chunk verbatim — no \\n appended. Use to simulate floating
        UART garbage that has no line terminator.
        """
        self._rx_queue.put(chunk)

    def close(self) -> None:
        self._closed = True

    @property
    def is_open(self) -> bool:
        return not self._closed
