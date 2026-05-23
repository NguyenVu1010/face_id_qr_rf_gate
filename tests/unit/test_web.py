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


def test_diag_ping_ok(setup):
    app, _db, _hub, uart, _ = setup
    uart.send_cmd.return_value = {"echo": "pong"}
    with app.test_client() as c:
        r = c.post("/api/diag/ping")
        assert r.status_code == 200
        body = r.get_json()
        assert "ack_ms" in body and isinstance(body["ack_ms"], int)
        assert body["data"] == {"echo": "pong"}
    uart.send_cmd.assert_called_once_with("ping", timeout=2.0)


def test_diag_status_link_down(setup):
    app, _, _, uart, _ = setup
    from smart_gate.link.uart_client import LinkDown
    uart.send_cmd.side_effect = LinkDown()
    with app.test_client() as c:
        r = c.post("/api/diag/status")
        assert r.status_code == 503
        body = r.get_json()
        assert "error" in body


def test_events_json_filter_method(tmp_data_dir):
    from unittest.mock import MagicMock
    db = Database(tmp_data_dir / "fm.db"); db.migrate()
    db.insert_event("face", None, True)
    db.insert_event("qr", None, True)
    db.insert_event("rfid", None, True)
    hub = MagicMock(); hub.wait_jpeg.return_value = PLACEHOLDER
    uart = MagicMock(); uart.link_alive.return_value = True
    app = create_app(db=db, hub=hub, uart=uart, data_dir=tmp_data_dir)
    with app.test_client() as c:
        r = c.get("/events.json?method=face&method=qr")
        rows = r.get_json()
        methods = sorted(row["method"] for row in rows)
        assert methods == ["face", "qr"]


def test_events_json_filter_granted(setup):
    app, db, *_ = setup
    db.insert_event("face", None, False)
    with app.test_client() as c:
        denied = c.get("/events.json?granted=0").get_json()
        granted = c.get("/events.json?granted=1").get_json()
    assert all(row["granted"] is False for row in denied)
    assert all(row["granted"] is True for row in granted)


def test_events_json_filter_q(tmp_data_dir):
    from unittest.mock import MagicMock
    db = Database(tmp_data_dir / "fq.db"); db.migrate()
    db.insert_user("alice"); db.insert_user("bob")
    a, b = db.get_user_id_by_name("alice"), db.get_user_id_by_name("bob")
    db.insert_event("face", a, True); db.insert_event("face", b, True)
    hub = MagicMock(); hub.wait_jpeg.return_value = PLACEHOLDER
    uart = MagicMock(); uart.link_alive.return_value = True
    app = create_app(db=db, hub=hub, uart=uart, data_dir=tmp_data_dir)
    with app.test_client() as c:
        rows = c.get("/events.json?q=ali").get_json()
    assert len(rows) == 1 and rows[0]["user_name"] == "alice"


def test_events_json_html_has_data_event_id(setup):
    app, *_ = setup
    with app.test_client() as c:
        r = c.get("/events.json?format=html")
        assert r.status_code == 200
        assert b'<tr data-event-id="' in r.data


def test_events_json_period_today(setup):
    app, *_ = setup
    with app.test_client() as c:
        rows = c.get("/events.json?period=today").get_json()
    # setup inserted one event "today" (default ts=datetime('now'))
    assert len(rows) == 1


def test_healthz_html_statusbar(setup):
    app, *_ = setup
    with app.test_client() as c:
        r = c.get("/healthz?format=html&panel=statusbar")
        assert r.status_code == 200
        assert b'id="statusbar"' in r.data
        assert b"LINK" in r.data


def test_healthz_html_banner_hidden_when_link_alive(setup):
    app, *_ = setup
    with app.test_client() as c:
        r = c.get("/healthz?format=html&panel=banner")
        assert r.status_code == 200
        assert b'id="link-banner"' in r.data
        assert b"Link down" not in r.data


def test_healthz_html_banner_shown_when_link_down(setup):
    app, _, _, uart, _ = setup
    uart.link_alive.return_value = False
    with app.test_client() as c:
        r = c.get("/healthz?format=html&panel=banner")
        assert b"Link down" in r.data


def test_healthz_html_quickstats(setup):
    app, *_ = setup
    with app.test_client() as c:
        r = c.get("/healthz?format=html&panel=quickstats")
        assert b"cap fps" in r.data
        assert b"det fps" in r.data
        assert b"frame age" in r.data
        assert b"events today" in r.data


def test_healthz_html_systemcards(setup):
    app, *_ = setup
    with app.test_client() as c:
        r = c.get("/healthz?format=html&panel=systemcards")
        assert b"LINK" in r.data
        assert b"CAP" in r.data
        assert b"DET" in r.data
        assert b"DISK" in r.data


def test_healthz_json_still_works_after_html_dispatcher(setup):
    """JSON must remain the default response and preserve all fields."""
    app, *_ = setup
    with app.test_client() as c:
        body = c.get("/healthz").get_json()
        for key in ("uptime_s", "link_alive", "last_frame_ago_s",
                    "threads_ok", "enrolled_users", "cap_fps", "det_fps",
                    "events_today", "disk_free_gb", "last_grant"):
            assert key in body, f"missing {key}"


def test_events_page_renders(setup):
    app, *_ = setup
    with app.test_client() as c:
        r = c.get("/events")
        assert r.status_code == 200
        assert b"Events" in r.data


def test_system_page_renders(setup):
    app, *_ = setup
    with app.test_client() as c:
        r = c.get("/system")
        assert r.status_code == 200
        assert b"System" in r.data
