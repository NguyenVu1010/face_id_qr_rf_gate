import pytest
from smart_gate.link.protocol import (
    encode, decode, ProtocolError, MAX_LINE, VERBS_CMD, VERBS_EVT,
)


def test_encode_cmd_with_data_and_id():
    line = encode("cmd", "open", {"user": "alice", "reason": "face"}, msg_id=42)
    assert line.endswith(b"\n")
    assert b'"id":42' in line
    assert b'"type":"cmd"' in line
    assert b'"v":"open"' in line
    assert b'"user":"alice"' in line


def test_encode_evt_without_id():
    line = encode("evt", "heartbeat", {"uptime_s": 100})
    assert b'"id"' not in line
    assert b'"type":"evt"' in line


def test_encode_nullary_no_data():
    line = encode("cmd", "ping", msg_id=1)
    assert b'"data"' not in line


def test_encode_too_long_raises():
    big = "x" * (MAX_LINE + 100)
    with pytest.raises(ProtocolError, match="too long"):
        encode("cmd", "open", {"big": big}, msg_id=1)


def test_decode_happy_path():
    obj = decode(b'{"id":1,"type":"ack","v":"open","data":{"ok":true}}\n')
    assert obj["id"] == 1
    assert obj["type"] == "ack"
    assert obj["v"] == "open"
    assert obj["data"]["ok"] is True


def test_decode_strips_crlf():
    obj = decode(b'{"type":"evt","v":"boot","data":{}}\r\n')
    assert obj["v"] == "boot"


def test_decode_empty_raises():
    with pytest.raises(ProtocolError, match="empty"):
        decode(b"\n")


def test_decode_too_long_raises():
    long_line = b'{"type":"cmd","v":"open","data":"' + b"x" * (MAX_LINE + 100) + b'"}\n'
    with pytest.raises(ProtocolError, match="too long"):
        decode(long_line)


def test_decode_bad_json_raises():
    with pytest.raises(ProtocolError, match="bad json"):
        decode(b'{not json}\n')


def test_decode_missing_required_field_raises():
    with pytest.raises(ProtocolError, match="missing"):
        decode(b'{"type":"cmd"}\n')


def test_decode_bad_type_raises():
    with pytest.raises(ProtocolError, match="bad type"):
        decode(b'{"type":"hello","v":"open"}\n')


def test_verbs_sets_are_disjoint():
    assert VERBS_CMD.isdisjoint(VERBS_EVT)
    assert "open" in VERBS_CMD
    assert "heartbeat" in VERBS_EVT
