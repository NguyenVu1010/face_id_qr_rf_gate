"""JSON Lines codec for the Pi <-> ESP32 UART link.

One message = one line of UTF-8 JSON terminated by \\n.
See docs/superpowers/specs/2026-05-21-smart-gate-architecture-design.md §4.
"""
from __future__ import annotations

import json

# ESP UART_LINE_MAX is 512; doubled for margin so a misbehaving / floating
# ESP UART pumping non-\n bytes cannot grow an unbounded bytearray inside
# the Pi rx loop. encode() and decode() also enforce this limit, so any
# real protocol message must fit.
MAX_LINE = 1024

VERBS_CMD = frozenset({
    "open", "close", "add_uid", "remove_uid", "list_uids",
    "config", "status", "ping",
})
VERBS_EVT = frozenset({
    "boot", "rfid", "gate", "person_passed", "heartbeat", "log",
})
_VALID_TYPES = {"cmd", "evt", "ack"}


class ProtocolError(ValueError):
    pass


def encode(typ: str, v: str, data: dict | None = None,
           msg_id: int | None = None) -> bytes:
    obj: dict = {}
    if msg_id is not None:
        obj["id"] = msg_id
    obj["type"] = typ
    obj["v"] = v
    if data is not None:
        obj["data"] = data
    line = (json.dumps(obj, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    if len(line) > MAX_LINE:
        raise ProtocolError(f"line too long: {len(line)} > {MAX_LINE}")
    return line


def decode(line: bytes) -> dict:
    line = line.rstrip(b"\r\n")
    if not line:
        raise ProtocolError("empty line")
    if len(line) + 1 > MAX_LINE:                # +1 for the \n
        raise ProtocolError(f"line too long: {len(line) + 1}")
    try:
        obj = json.loads(line)
    except (json.JSONDecodeError, UnicodeDecodeError, UnicodeError) as e:
        # json.loads on bytes auto-detects encoding via BOM/heuristics. Random
        # garbage bytes (e.g. floating UART RX before the ESP32 is flashed)
        # can drive the auto-detector into utf-32-be and raise UnicodeDecodeError
        # which is NOT a JSONDecodeError. Treat all of them as ProtocolError so
        # the rx loop can drop the line and move on.
        raise ProtocolError(f"bad json: {e}") from e
    if not isinstance(obj, dict):
        raise ProtocolError("not a json object")
    if "type" not in obj or "v" not in obj:
        raise ProtocolError("missing required field (type or v)")
    if obj["type"] not in _VALID_TYPES:
        raise ProtocolError(f"bad type: {obj['type']}")
    return obj
