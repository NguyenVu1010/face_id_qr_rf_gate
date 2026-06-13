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
    # Mock gate_tracker that always confirms (so /api/gate/open returns 200
    # without waiting). Tests for the unconfirmed path set this explicitly.
    gate_tracker = MagicMock()
    gate_tracker.wait_for_state.return_value = True
    gate_tracker.snapshot.return_value = {"state": "idle", "since_s": 0,
                                          "last_user": None}
    app = create_app(db=db, hub=hub, uart=uart, data_dir=tmp_data_dir,
                     gate_tracker=gate_tracker, confirm_timeout_s=0.05)
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


def test_api_users_list_returns_id_name_pairs(setup):
    """/api/users.json powers the dashboard RFID-bind dropdown."""
    app, db, *_ = setup
    db.insert_user("bob")
    with app.test_client() as c:
        r = c.get("/api/users.json")
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data, list)
        names = [u["name"] for u in data]
        assert "alice" in names
        assert "bob" in names
        for u in data:
            assert "id" in u and isinstance(u["id"], int)
            assert "name" in u and isinstance(u["name"], str)
            # Only id+name should leak — no created_at / counts / etc.
            assert set(u.keys()) == {"id", "name"}


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


def test_gate_open_ack_but_no_state_change_504(tmp_data_dir):
    """ESP32 acks the cmd but the servo never transitions to 'open' →
    returns 504, NO DB event row written, audit log warns the user."""
    db = Database(tmp_data_dir / "w.db")
    db.migrate()
    hub = MagicMock(); hub.wait_jpeg.return_value = PLACEHOLDER
    uart = MagicMock()
    uart.send_cmd.return_value = {"ok": True}
    uart.link_alive.return_value = True
    gate_tracker = MagicMock()
    gate_tracker.wait_for_state.return_value = False   # never confirmed
    gate_tracker.snapshot.return_value = {"state": "opening", "since_s": 3,
                                          "last_user": None}
    app = create_app(db=db, hub=hub, uart=uart, data_dir=tmp_data_dir,
                     gate_tracker=gate_tracker, confirm_timeout_s=0.05)
    app.testing = True
    with app.test_client() as c:
        r = c.post("/api/gate/open")
        assert r.status_code == 504, r.data
        body = r.get_json()
        assert body["ok"] is False
        assert "did not reach state=open" in body["error"]
    # critically: no event row was inserted for the unconfirmed open
    rows = db.recent_events()
    assert not any(r[2] == "manual_open" for r in rows)


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


def test_events_json_period_today_uses_utc_boundary(tmp_data_dir, monkeypatch):
    """Deterministic TZ-boundary regression test.

    Freezes wall clock at 2026-06-10 17:00 UTC (= 2026-06-11 00:00 +07).
    Inserts an event with ts = 2026-06-10 16:00 UTC (= 23:00 +07 on the prior
    local day, but still inside today's UTC window).

    With the UTC fix:
      since = 2026-06-10 00:00 UTC  →  16:00 UTC row is included.
    With the pre-fix bug (naive datetime.now() on Asia/Ho_Chi_Minh):
      since = 2026-06-11 00:00 (local clock interpreted as UTC string)
            → 16:00 UTC row would be excluded → test fails.

    Uses monkeypatch since freezegun is not in test deps.
    """
    import datetime as _dt
    from unittest.mock import MagicMock
    from smart_gate.web import app as web_app

    fixed_now = _dt.datetime(2026, 6, 10, 17, 0, 0, tzinfo=_dt.timezone.utc)
    # Simulate Asia/Ho_Chi_Minh (UTC+7) as the local zone. The whole point of
    # this test is that on UTC+7 the naive `.now()` returns a local time that
    # is 7h ahead of UTC, which the broken code then treats as if it were UTC.
    local_tz = _dt.timezone(_dt.timedelta(hours=7))

    class FakeDateTime(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is not None:
                return fixed_now.astimezone(tz)
            # Naive `.now()` returns LOCAL wall-clock with tzinfo stripped —
            # this is what reproduces the production bug.
            return fixed_now.astimezone(local_tz).replace(tzinfo=None)

    # The events_json view does `import datetime as _dt` locally, so we need
    # to patch the real datetime module's class (or pre-import the module
    # and patch its attribute). The view's `_dt.datetime` resolves through
    # the shared `datetime` module, so patching there is the cleanest hook.
    monkeypatch.setattr("datetime.datetime", FakeDateTime)

    db = Database(tmp_data_dir / "tz.db")
    db.migrate()
    # Insert via direct SQL so we can set ts explicitly (UTC).
    db.insert_user("tz_boundary")
    uid = db.get_user_id_by_name("tz_boundary")
    db.connect().execute(
        "INSERT INTO events (ts, method, user_id, granted) "
        "VALUES (?, ?, ?, ?)",
        ("2026-06-10 16:00:00", "test", uid, 1),
    )
    db.connect().commit()

    hub = MagicMock(); hub.wait_jpeg.return_value = PLACEHOLDER
    uart = MagicMock(); uart.link_alive.return_value = True
    app = web_app.create_app(db=db, hub=hub, uart=uart, data_dir=tmp_data_dir)
    app.testing = True
    with app.test_client() as c:
        resp = c.get("/events.json?period=today")
        assert resp.status_code == 200
        rows = resp.get_json()
    assert any(r["user_name"] == "tz_boundary" for r in rows), \
        "UTC event at 16:00 should be inside today's UTC window from 17:00 UTC"


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


def test_base_has_topbar_and_banner(setup):
    app, *_ = setup
    with app.test_client() as c:
        r = c.get("/")
        assert r.status_code == 200
        assert b'id="statusbar"' in r.data
        assert b'id="link-banner"' in r.data
        assert b'href="/events"' in r.data
        assert b'href="/system"' in r.data
        assert b'app.css' in r.data
        assert b'pico' not in r.data


def test_dashboard_has_stream_quickstats_events(setup):
    """New design-system markup is in place."""
    app, *_ = setup
    with app.test_client() as c:
        r = c.get("/")
        assert b"Live preview" in r.data
        assert b'src="/stream.mjpeg"' in r.data
        assert b"Open gate" in r.data
        assert b"Close" in r.data
        assert b'id="quickstats"' in r.data
        assert b'id="events-tbody"' in r.data
        assert b'href="/events"' in r.data


def test_dashboard_preserves_enroll_button(setup):
    """The 'Tạo user mới' / /api/enroll workflow must survive the rewrite."""
    app, *_ = setup
    with app.test_client() as c:
        r = c.get("/")
        assert b'hx-post="/api/enroll"' in r.data
        assert b'face_capture' in r.data           # hx-vals
        assert b'enroll-result' in r.data          # response card target


def test_dashboard_preserves_gate_badge(setup):
    """The gate state badge polling /api/gate/state.json must remain."""
    app, *_ = setup
    with app.test_client() as c:
        r = c.get("/")
        assert b'gate-badge' in r.data
        assert b'/api/gate/state.json' in r.data


def test_events_page_has_filter_form(setup):
    app, *_ = setup
    with app.test_client() as c:
        r = c.get("/events")
        assert b'id="event-filter"' in r.data
        assert b'name="method"' in r.data
        assert b'name="granted"' in r.data
        assert b'name="q"' in r.data
        assert b'name="period"' in r.data


def test_events_page_has_clip_modal(setup):
    app, *_ = setup
    with app.test_client() as c:
        r = c.get("/events")
        assert b'id="clip-modal"' in r.data
        assert b'id="clip-video"' in r.data
        assert b'id="events-live"' in r.data


def test_users_page_empty_state(tmp_data_dir):
    from unittest.mock import MagicMock
    db = Database(tmp_data_dir / "e.db"); db.migrate()
    hub = MagicMock(); hub.wait_jpeg.return_value = PLACEHOLDER
    uart = MagicMock(); uart.link_alive.return_value = True
    app = create_app(db=db, hub=hub, uart=uart, data_dir=tmp_data_dir)
    with app.test_client() as c:
        r = c.get("/users")
        decoded = r.data.decode("utf-8", "ignore")
        assert "No users enrolled" in decoded or "Chưa có user" in decoded


def test_users_page_counts_users(setup):
    app, db, *_ = setup
    with app.test_client() as c:
        r = c.get("/users")
        assert b"1 enrolled" in r.data
        assert b"alice" in r.data


def test_users_page_preserves_qr_thumbnail(setup):
    """The QR column with 60x60 thumbnail and ?download=1 button must survive."""
    app, db, *_ = setup
    # Setup fixture inserts alice (no QR by default). Add a QR token so the
    # 'has_qr' flag becomes truthy.
    db.insert_qr_token("a" * 32, db.get_user_id_by_name("alice"))
    with app.test_client() as c:
        r = c.get("/users")
        # Thumbnail link to /qr/alice.png
        assert b'/qr/alice.png' in r.data
        # Download button ?download=1
        assert b'?download=1' in r.data


def test_users_page_has_delete_button(setup):
    app, *_ = setup
    with app.test_client() as c:
        r = c.get("/users")
        assert b'hx-delete="/api/users/alice"' in r.data
        assert b'data-user="alice"' in r.data


def test_delete_user_ok(setup):
    app, db, *_ = setup
    with app.test_client() as c:
        r = c.delete("/api/users/alice")
        assert r.status_code == 200, r.data
        body = r.get_json()
        assert body == {"ok": True, "name": "alice"}
    assert db.get_user_id_by_name("alice") is None


def test_delete_user_not_found(setup):
    app, *_ = setup
    with app.test_client() as c:
        r = c.delete("/api/users/nobody")
        assert r.status_code == 404


def test_delete_user_invalid_name(setup):
    app, *_ = setup
    with app.test_client() as c:
        r = c.delete("/api/users/../etc/passwd")
        # Flask route matches names only — anything with '/' is a different
        # route. The 404 comes from werkzeug routing, not our handler. Either
        # 404 or 400 is acceptable; we just want no traversal to succeed.
        assert r.status_code in (400, 404)


def test_delete_user_post_action_required(setup):
    app, *_ = setup
    with app.test_client() as c:
        # POST without action=delete must NOT delete
        r = c.post("/api/users/alice")
        assert r.status_code == 405
        # POST with action=delete works
        r = c.post("/api/users/alice?action=delete")
        assert r.status_code == 200


def test_system_page_has_cards_and_log(setup):
    app, *_ = setup
    with app.test_client() as c:
        r = c.get("/system")
        assert b'id="systemcards"' in r.data
        assert b'id="esp-log"' in r.data
        assert b'id="sse-status"' in r.data
        assert b'data-diag="ping"' in r.data
        assert b'data-diag="status"' in r.data


# ---------------------------------------------------------------------------
# Numeric query-param clamping (_int_param) — Task 2.7
# Guards against SQLite ``LIMIT -1 = no limit`` exfiltrating the table.
# ---------------------------------------------------------------------------
def test_events_negative_limit_returns_400(setup):
    app, *_ = setup
    with app.test_client() as c:
        resp = c.get("/events.json?limit=-1")
        assert resp.status_code == 400


def test_events_huge_limit_capped(setup):
    app, *_ = setup
    with app.test_client() as c:
        resp = c.get("/events.json?limit=99999")
        # Should NOT 500; should clamp internally to <= 500
        assert resp.status_code == 200


def test_events_non_numeric_limit_returns_400(setup):
    app, *_ = setup
    with app.test_client() as c:
        resp = c.get("/events.json?limit=abc")
        assert resp.status_code == 400


def test_esp_log_negative_limit_returns_400(setup):
    app, *_ = setup
    with app.test_client() as c:
        resp = c.get("/api/esp_log?limit=-1")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# RFID UID enrollment — POST /api/users/<name>/rfid + DELETE counterpart
# ---------------------------------------------------------------------------
def test_add_rfid_uid_happy_path(setup):
    """POST /api/users/alice/rfid → cmd:add_uid sent, UID lowercased."""
    app, _db, _hub, uart, _ = setup
    uart.send_cmd.reset_mock()
    uart.send_cmd.return_value = {"count": 1}
    with app.test_client() as c:
        r = c.post("/api/users/alice/rfid", json={"uid": "23AC9F11"})
        assert r.status_code == 200, r.data
        body = r.get_json()
        assert body["ok"] is True
        assert body["uid"] == "23ac9f11"
        assert body["name"] == "alice"
        assert body["ack"] == {"count": 1}
    uart.send_cmd.assert_called_once_with(
        "add_uid", {"uid": "23ac9f11", "name": "alice"}, timeout=2.0)


def test_add_rfid_uid_accepts_7byte_uid(setup):
    """ISO 14443 7-byte UIDs are 14 hex chars — must be accepted."""
    app, _, _, uart, _ = setup
    uart.send_cmd.reset_mock()
    uart.send_cmd.return_value = {"count": 1}
    with app.test_client() as c:
        r = c.post("/api/users/alice/rfid", json={"uid": "04A1B2C3D4E5F6"})
        assert r.status_code == 200
    payload = uart.send_cmd.call_args[0][1]
    assert payload["uid"] == "04a1b2c3d4e5f6"


def test_add_rfid_uid_rejects_bad_hex(setup):
    app, *_ = setup
    with app.test_client() as c:
        r = c.post("/api/users/alice/rfid", json={"uid": "not-hex!"})
        assert r.status_code == 400


def test_add_rfid_uid_rejects_too_short(setup):
    """7 hex chars (< 8) should be rejected."""
    app, *_ = setup
    with app.test_client() as c:
        r = c.post("/api/users/alice/rfid", json={"uid": "1234567"})
        assert r.status_code == 400


def test_add_rfid_uid_rejects_too_long(setup):
    """21 hex chars (> 20) should be rejected."""
    app, *_ = setup
    with app.test_client() as c:
        r = c.post("/api/users/alice/rfid",
                   json={"uid": "1" * 21})
        assert r.status_code == 400


def test_add_rfid_uid_rejects_missing_uid(setup):
    app, *_ = setup
    with app.test_client() as c:
        r = c.post("/api/users/alice/rfid", json={})
        assert r.status_code == 400


def test_add_rfid_uid_rejects_unknown_user(setup):
    app, _, _, uart, _ = setup
    uart.send_cmd.reset_mock()
    with app.test_client() as c:
        r = c.post("/api/users/does_not_exist/rfid",
                   json={"uid": "23ac9f11"})
        assert r.status_code == 404
    uart.send_cmd.assert_not_called()


def test_add_rfid_uid_handles_link_timeout(setup):
    """send_cmd raises LinkTimeout → 503 with error body."""
    app, _, _, uart, _ = setup
    from smart_gate.link.uart_client import LinkTimeout
    uart.send_cmd.side_effect = LinkTimeout("no ack for add_uid")
    with app.test_client() as c:
        r = c.post("/api/users/alice/rfid", json={"uid": "23ac9f11"})
        assert r.status_code == 503
        assert "no ack" in r.get_json()["error"]


def test_add_rfid_uid_handles_link_down(setup):
    app, _, _, uart, _ = setup
    from smart_gate.link.uart_client import LinkDown
    uart.send_cmd.side_effect = LinkDown("serial closed")
    with app.test_client() as c:
        r = c.post("/api/users/alice/rfid", json={"uid": "23ac9f11"})
        assert r.status_code == 503


def test_add_rfid_uid_invalid_name_format(setup):
    """Path-traversal-y name → 400 before any DB or UART work."""
    app, _, _, uart, _ = setup
    uart.send_cmd.reset_mock()
    with app.test_client() as c:
        # werkzeug routing will reject names with '/', so test with a name
        # that hits our route but fails our format check.
        r = c.post("/api/users/has spaces/rfid", json={"uid": "23ac9f11"})
        # Either werkzeug 404 (route mismatch) or our 400 — both prove the
        # bad name never reached send_cmd.
        assert r.status_code in (400, 404)
    uart.send_cmd.assert_not_called()


def test_remove_rfid_uid_happy_path(setup):
    app, _, _, uart, _ = setup
    uart.send_cmd.reset_mock()
    uart.send_cmd.return_value = {"removed": True}
    with app.test_client() as c:
        r = c.delete("/api/users/alice/rfid/23AC9F11")
        assert r.status_code == 200, r.data
        body = r.get_json()
        assert body["ok"] is True
        assert body["uid"] == "23ac9f11"
    uart.send_cmd.assert_called_once_with(
        "remove_uid", {"uid": "23ac9f11"}, timeout=2.0)


def test_remove_rfid_uid_rejects_bad_hex(setup):
    app, _, _, uart, _ = setup
    uart.send_cmd.reset_mock()
    with app.test_client() as c:
        r = c.delete("/api/users/alice/rfid/zzzz")
        assert r.status_code == 400
    uart.send_cmd.assert_not_called()


def test_remove_rfid_uid_unknown_user(setup):
    app, _, _, uart, _ = setup
    uart.send_cmd.reset_mock()
    with app.test_client() as c:
        r = c.delete("/api/users/nobody/rfid/23ac9f11")
        assert r.status_code == 404
    uart.send_cmd.assert_not_called()


def test_users_page_has_rfid_form(setup):
    """The /users page must render a per-user RFID input + button."""
    app, *_ = setup
    with app.test_client() as c:
        r = c.get("/users")
        assert r.status_code == 200
        assert b"rfid-input-" in r.data
        assert b"rfid-form" in r.data
        assert b"addRfid" in r.data
