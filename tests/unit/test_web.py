import io
import threading
from unittest.mock import MagicMock
import pytest
from smart_gate.data.db import Database
from smart_gate.web.app import create_app


PLACEHOLDER = b"\xff\xd8\xff\xd9"          # tiny valid-ish JPEG markers


@pytest.fixture
def setup(tmp_data_dir):
    db = Database(tmp_data_dir / "web.db")
    db.migrate()
    db.insert_user("alice")
    uid = db.get_user_id_by_name("alice")
    db.insert_event("face", uid, True, detail='{"distance":0.4}')
    hub = MagicMock()
    hub.wait_jpeg.return_value = PLACEHOLDER
    uart = MagicMock()
    uart.send_cmd.return_value = {"ok": True}
    uart.link_alive.return_value = True
    app = create_app(db=db, hub=hub, uart=uart, data_dir=tmp_data_dir)
    app.testing = True
    return app, db, hub, uart, tmp_data_dir


def test_dashboard_renders(setup):
    app, *_ = setup
    with app.test_client() as c:
        r = c.get("/")
        assert r.status_code == 200
        assert b"Live" in r.data


def test_users_page(setup):
    app, *_ = setup
    with app.test_client() as c:
        r = c.get("/users")
        assert r.status_code == 200
        assert b"alice" in r.data


def test_events_json(setup):
    app, *_ = setup
    with app.test_client() as c:
        r = c.get("/events.json")
        assert r.status_code == 200
        body = r.get_json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["method"] == "face"
        assert body[0]["user_name"] == "alice"


def test_gate_open_ok(setup):
    app, db, hub, uart, _ = setup
    with app.test_client() as c:
        r = c.post("/api/gate/open")
        assert r.status_code == 200
    uart.send_cmd.assert_called_once_with(
        "open", {"user": "admin", "reason": "manual"}, timeout=2.0)
    rows = db.recent_events()
    assert any(r[2] == "manual_open" for r in rows)


def test_gate_open_link_down(setup):
    app, _, _, uart, _ = setup
    from smart_gate.link.uart_client import LinkDown
    uart.send_cmd.side_effect = LinkDown()
    with app.test_client() as c:
        r = c.post("/api/gate/open")
        assert r.status_code == 503


def test_clip_missing_returns_404(setup):
    app, *_ = setup
    with app.test_client() as c:
        r = c.get("/clips/9999.mp4")
        assert r.status_code == 404


def test_healthz(setup):
    app, _db, hub, _uart, _data_dir = setup
    hub._last_publish_mono = None        # MagicMock would otherwise satisfy 'is not None'
    with app.test_client() as c:
        r = c.get("/healthz")
        assert r.status_code == 200
        body = r.get_json()
        assert body["link_alive"] is True
        assert "uptime_s" in body
        assert "last_frame_ago_s" in body
        assert "threads_ok" in body


def test_clip_serves_correct_event(setup):
    app, db, _hub, _uart, data_dir = setup
    eid_old = db.insert_event("face", None, True)
    eid_new = db.insert_event("face", None, True)
    db.update_event_clip(eid_old, f"clips/{eid_old}.mp4")
    (data_dir / "clips").mkdir(exist_ok=True)
    (data_dir / f"clips/{eid_old}.mp4").write_bytes(b"OLDCLIP")
    with app.test_client() as c:
        r = c.get(f"/clips/{eid_old}.mp4")
        assert r.status_code == 200
        assert r.data == b"OLDCLIP"
        r2 = c.get(f"/clips/{eid_new}.mp4")
        assert r2.status_code == 404


def test_healthz_extended_fields(setup):
    app, db, _hub, _uart, _ = setup
    with app.test_client() as c:
        r = c.get("/healthz")
        body = r.get_json()
        for key in ("cap_fps", "det_fps", "events_today",
                    "disk_free_gb", "last_grant"):
            assert key in body, f"missing {key}"
        # last_grant is None or a dict with name+ts
        if body["last_grant"] is not None:
            assert "name" in body["last_grant"]
            assert "ts" in body["last_grant"]


def test_healthz_preserves_enrolled_users(setup):
    """enrolled_users must still be present after the extension."""
    app, *_ = setup
    with app.test_client() as c:
        body = c.get("/healthz").get_json()
        assert "enrolled_users" in body


def test_healthz_events_today_counts_inserts(tmp_data_dir):
    from unittest.mock import MagicMock
    db = Database(tmp_data_dir / "h.db"); db.migrate()
    db.insert_event("face", None, True)
    db.insert_event("face", None, True)
    hub = MagicMock(); hub.wait_jpeg.return_value = PLACEHOLDER
    uart = MagicMock(); uart.link_alive.return_value = True
    app = create_app(db=db, hub=hub, uart=uart, data_dir=tmp_data_dir)
    with app.test_client() as c:
        r = c.get("/healthz")
        assert r.get_json()["events_today"] == 2


def test_healthz_last_grant_present(setup):
    app, db, *_ = setup
    # setup already inserted one granted face for alice
    with app.test_client() as c:
        body = c.get("/healthz").get_json()
        assert body["last_grant"] is not None
        assert body["last_grant"]["name"] == "alice"
