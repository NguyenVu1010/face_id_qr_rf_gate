"""JSON Lines codec for the Pi <-> ESP32 UART link.

One message = one line of UTF-8 JSON terminated by \\n. Max 512 bytes.
See docs/superpowers/specs/2026-05-21-smart-gate-architecture-design.md §4.
"""
from __future__ import annotations

import json

MAX_LINE = 512

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
    except json.JSONDecodeError as e:
        raise ProtocolError(f"bad json: {e}") from e
    if not isinstance(obj, dict):
        raise ProtocolError("not a json object")
    if "type" not in obj or "v" not in obj:
        raise ProtocolError("missing required field (type or v)")
    if obj["type"] not in _VALID_TYPES:
        raise ProtocolError(f"bad type: {obj['type']}")
    return obj
