"""UART client: rx, tx, heartbeat threads + reconnect.

Designed for testability: the serial constructor is wrapped by _open_serial
so tests can monkeypatch it with a FakeSerial.
"""
from __future__ import annotations

import dataclasses
import itertools
import logging
import queue
import threading
import time
from typing import Any

from smart_gate.link import protocol

try:
    import serial as _pyserial
    _real_SerialException = _pyserial.SerialException
except Exception:
    _pyserial = None
    class _real_SerialException(Exception): ...

SerialException: type[Exception] = _real_SerialException


def _open_serial(port: str, baud: int, timeout: float = 1.0):
    """Open a pyserial port without toggling DTR/RTS.

    On boards using CP2102/CH340 USB-UART (typical ESP32 DevKits), DTR is wired
    to the EN line so a port open with default DTR=HIGH resets the ESP32. We
    explicitly disable hardware flow control and force DTR/RTS low after the
    port is open so the daemon does not reboot the ESP32 every time it
    reconnects.
    """
    if _pyserial is None:
        raise RuntimeError("pyserial not installed")
    ser = _pyserial.Serial(port, baud, timeout=timeout,
                           dsrdtr=False, rtscts=False)
    try:
        ser.dtr = False
        ser.rts = False
    except (AttributeError, OSError):
        pass
    return ser


log = logging.getLogger(__name__)


class LinkDown(Exception): pass
class LinkTimeout(Exception): pass


@dataclasses.dataclass
class EspEvent:
    v: str
    data: dict


_SENTINEL = object()


class UartClient:
    def __init__(self, port: str, baud: int, event_bus: queue.Queue,
                 shutdown: threading.Event, ping_interval_s: float = 5.0,
                 heartbeat_timeout_s: float = 30.0):
        self._port = port
        self._baud = baud
        self._bus = event_bus
        self._shutdown = shutdown
        self._ping_interval = ping_interval_s
        self._hb_timeout = heartbeat_timeout_s

        self._ser = None
        self._port_lock = threading.Lock()
        self._tx_queue: queue.Queue = queue.Queue()
        self._next_id = itertools.count(1)
        self._pending: dict[int, tuple[threading.Event, dict]] = {}
        self._pending_lock = threading.Lock()
        self._last_rx = 0.0
        self._connected = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        for target, name in [
            (self._rx_loop, "uart-rx"),
            (self._tx_loop, "uart-tx"),
            (self._heartbeat_loop, "uart-hb"),
        ]:
            t = threading.Thread(target=target, name=name, daemon=True)
            t.start()
            self._threads.append(t)

    def join(self, timeout: float | None = None) -> None:
        self._tx_queue.put(_SENTINEL)
        for t in self._threads:
            t.join(timeout=timeout)

    def link_alive(self) -> bool:
        return (self._connected.is_set()
                and (time.monotonic() - self._last_rx) < self._hb_timeout)

    def send_cmd(self, verb: str, data: dict | None = None,
                 timeout: float = 2.0) -> dict | None:
        msg_id = next(self._next_id)
        payload = protocol.encode("cmd", verb, data, msg_id)
        ack_event = threading.Event()
        holder: dict[str, Any] = {}
        self._tx_queue.put((msg_id, payload, ack_event, holder))
        if not ack_event.wait(timeout):
            with self._pending_lock:
                self._pending.pop(msg_id, None)
            raise LinkTimeout(f"no ack for {verb} id={msg_id}")
        if "err" in holder:
            raise holder["err"]
        return holder.get("data")

    def _reconnect(self) -> None:
        delay = 1.0
        while not self._shutdown.is_set():
            try:
                self._ser = _open_serial(self._port, self._baud, timeout=1.0)
                self._connected.set()
                self._last_rx = time.monotonic()
                log.info("link up: %s @ %d", self._port, self._baud)
                return
            except SerialException as e:
                self._ser = None
                self._connected.clear()
                log.warning("link open failed: %s; retry in %.1fs", e, delay)
                if self._shutdown.wait(delay):
                    return
                delay = min(30.0, delay * 2)

    def _rx_loop(self) -> None:
        while not self._shutdown.is_set():
            if self._ser is None:
                self._reconnect()
                if self._ser is None:
                    return
            try:
                line = self._ser.readline()
            except SerialException as e:
                log.warning("rx exception: %s", e)
                with self._port_lock:
                    self._ser = None
                self._connected.clear()
                continue
            if not line:
                continue
            try:
                msg = protocol.decode(line)
            except protocol.ProtocolError as e:
                log.warning("malformed line %r: %s", line, e)
                continue
            self._last_rx = time.monotonic()
            self._dispatch(msg)

    def _tx_loop(self) -> None:
        while not self._shutdown.is_set():
            try:
                item = self._tx_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is _SENTINEL:
                return
            msg_id, payload, ack_event, holder = item
            with self._port_lock:
                ser = self._ser
                if ser is None:
                    holder["err"] = LinkDown()
                    ack_event.set()
                    continue
                try:
                    ser.write(payload)
                except SerialException as e:
                    log.warning("tx exception: %s", e)
                    self._ser = None
                    self._connected.clear()
                    holder["err"] = LinkDown()
                    ack_event.set()
                    continue
            with self._pending_lock:
                self._pending[msg_id] = (ack_event, holder)

    def _heartbeat_loop(self) -> None:
        while not self._shutdown.wait(self._ping_interval):
            if not self._connected.is_set():
                continue
            try:
                self.send_cmd("ping", timeout=2.0)
            except (LinkTimeout, LinkDown):
                pass

    def _dispatch(self, msg: dict) -> None:
        typ = msg.get("type")
        if typ == "ack":
            mid = msg.get("id")
            with self._pending_lock:
                pending = self._pending.pop(mid, None)
            if pending:
                ack_event, holder = pending
                holder["data"] = msg.get("data")
                ack_event.set()
            return
        if typ == "evt":
            self._bus.put(EspEvent(v=msg.get("v"), data=msg.get("data") or {}))
            return
