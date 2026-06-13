"""Tests for /api/users/<name>/rfid management — helper + endpoints."""
from __future__ import annotations
from unittest.mock import Mock

import pytest

from smart_gate.link.uart_client import LinkDown, LinkTimeout


def _ack(uids):
    """Build a fake ack object matching what UartClient.send_cmd returns
    for the `list_uids` verb: a dict whose 'data' carries the uid list."""
    return {"data": {"uids": uids}}


def test_list_uids_for_user_filters_by_name():
    from smart_gate.web.app import _list_uids_for_user
    uart = Mock()
    uart.send_cmd.return_value = _ack([
        {"uid": "AAAA1111", "name": "alice"},
        {"uid": "BBBB2222", "name": "bob"},
        {"uid": "CCCC3333", "name": "alice"},
    ])
    assert _list_uids_for_user(uart, "alice") == ["AAAA1111", "CCCC3333"]


def test_list_uids_for_user_returns_empty_on_link_down():
    from smart_gate.web.app import _list_uids_for_user
    uart = Mock()
    uart.send_cmd.side_effect = LinkDown("no esp")
    assert _list_uids_for_user(uart, "alice") == []


def test_list_uids_for_user_returns_empty_on_timeout():
    from smart_gate.web.app import _list_uids_for_user
    uart = Mock()
    uart.send_cmd.side_effect = LinkTimeout("slow esp")
    assert _list_uids_for_user(uart, "alice") == []


def test_list_uids_for_user_returns_empty_on_malformed_ack():
    from smart_gate.web.app import _list_uids_for_user
    uart = Mock()
    uart.send_cmd.return_value = {"data": {}}
    assert _list_uids_for_user(uart, "alice") == []


def test_list_uids_for_user_none_uart():
    from smart_gate.web.app import _list_uids_for_user
    assert _list_uids_for_user(None, "alice") == []


def test_get_user_rfid_json(monkeypatch):
    """End-to-end: GET /api/users/<name>/rfid.json with a stubbed uart."""
    from smart_gate.web.app import create_app

    # Minimal mocks for the create_app contract
    db = Mock()
    db.get_user_id_by_name.return_value = 1
    hub = Mock()
    uart = Mock()
    uart.send_cmd.return_value = _ack([
        {"uid": "AAAA1111", "name": "alice"},
        {"uid": "CCCC3333", "name": "alice"},
        {"uid": "BBBB2222", "name": "bob"},
    ])

    app = create_app(db=db, hub=hub, uart=uart, data_dir="/tmp")
    app.config["TESTING"] = True
    client = app.test_client()

    r = client.get("/api/users/alice/rfid.json")
    assert r.status_code == 200
    assert r.get_json() == {"uids": ["AAAA1111", "CCCC3333"]}


def test_get_user_rfid_json_unknown_user():
    from smart_gate.web.app import create_app
    db = Mock()
    db.get_user_id_by_name.return_value = None
    hub = Mock()
    uart = Mock()

    app = create_app(db=db, hub=hub, uart=uart, data_dir="/tmp")
    client = app.test_client()

    r = client.get("/api/users/ghost/rfid.json")
    assert r.status_code == 404
    uart.send_cmd.assert_not_called()


def test_get_user_rfid_json_link_down(monkeypatch):
    from smart_gate.web.app import create_app
    db = Mock()
    db.get_user_id_by_name.return_value = 1
    hub = Mock()
    uart = Mock()
    uart.send_cmd.side_effect = LinkDown("no esp")

    app = create_app(db=db, hub=hub, uart=uart, data_dir="/tmp")
    client = app.test_client()

    r = client.get("/api/users/alice/rfid.json")
    # Helper returns [] on LinkDown; endpoint treats that as success-empty.
    # This is acceptable because the UI shows "no cards" either way.
    assert r.status_code == 200
    assert r.get_json() == {"uids": []}


def test_delete_user_cascades_remove_uid():
    """DELETE /api/users/<name> first removes ESP allowlist entries."""
    from smart_gate.web.app import create_app
    db = Mock()
    db.delete_user.return_value = True
    hub = Mock()
    uart = Mock()
    # First call (list_uids): two UIDs; subsequent calls (remove_uid each): ok
    uart.send_cmd.side_effect = [
        _ack([{"uid": "AAAA", "name": "alice"},
              {"uid": "BBBB", "name": "alice"}]),
        {"data": {"ok": True}},
        {"data": {"ok": True}},
    ]

    app = create_app(db=db, hub=hub, uart=uart, data_dir="/tmp")
    client = app.test_client()

    r = client.delete("/api/users/alice")
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert sorted(body["removed_uids"]) == ["AAAA", "BBBB"]
    assert body.get("failed_uids", []) == []
    # Verify the call ordering: list_uids then two remove_uid
    calls = uart.send_cmd.call_args_list
    assert calls[0].args[0] == "list_uids"
    assert calls[1].args[0] == "remove_uid"
    assert calls[2].args[0] == "remove_uid"
    db.delete_user.assert_called_once_with("alice")


def test_delete_user_link_down_still_deletes_sqlite():
    from smart_gate.web.app import create_app
    db = Mock()
    db.delete_user.return_value = True
    hub = Mock()
    uart = Mock()
    uart.send_cmd.side_effect = LinkDown("no esp")

    app = create_app(db=db, hub=hub, uart=uart, data_dir="/tmp")
    client = app.test_client()

    r = client.delete("/api/users/alice")
    assert r.status_code == 200
    body = r.get_json()
    assert body["removed_uids"] == []
    assert body.get("link_down") is True
    db.delete_user.assert_called_once_with("alice")


def test_delete_user_partial_uid_failure():
    from smart_gate.web.app import create_app
    db = Mock()
    db.delete_user.return_value = True
    hub = Mock()
    uart = Mock()
    # list_uids ok, first remove_uid ok, second raises
    uart.send_cmd.side_effect = [
        _ack([{"uid": "AAAA", "name": "alice"},
              {"uid": "BBBB", "name": "alice"}]),
        {"data": {"ok": True}},
        LinkTimeout("esp slow"),
    ]

    app = create_app(db=db, hub=hub, uart=uart, data_dir="/tmp")
    client = app.test_client()

    r = client.delete("/api/users/alice")
    assert r.status_code == 200
    body = r.get_json()
    assert body["removed_uids"] == ["AAAA"]
    assert body["failed_uids"] == ["BBBB"]
    db.delete_user.assert_called_once_with("alice")
