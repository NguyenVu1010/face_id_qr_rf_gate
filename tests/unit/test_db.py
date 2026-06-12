import sqlite3
import pytest
from smart_gate.data.db import Database


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "test.db")
    d.migrate()
    return d


def test_migrate_creates_tables(db):
    conn = db.connect()
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert {"users", "face_encodings", "qr_tokens", "events", "esp_log", "_meta"} <= tables


def test_migrate_idempotent(tmp_path):
    d = Database(tmp_path / "x.db")
    d.migrate()
    d.migrate()                                  # second call must not error
    conn = d.connect()
    ver = conn.execute("SELECT value FROM _meta WHERE key='schema_version'").fetchone()[0]
    assert ver == "1"


def test_wal_mode_enabled(db):
    conn = db.connect()
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_foreign_keys_on(db):
    conn = db.connect()
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1


def test_qr_partial_unique_one_active_per_user(db):
    conn = db.connect()
    conn.execute("INSERT INTO users(name) VALUES ('alice')")
    uid = conn.execute("SELECT id FROM users WHERE name='alice'").fetchone()[0]
    conn.execute("INSERT INTO qr_tokens(token, user_id) VALUES ('aaa', ?)", (uid,))
    # Second active token for same user must fail
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO qr_tokens(token, user_id) VALUES ('bbb', ?)", (uid,))
    # But revoked + new active is OK
    conn.execute("UPDATE qr_tokens SET revoked_at=datetime('now') WHERE token='aaa'")
    conn.execute("INSERT INTO qr_tokens(token, user_id) VALUES ('ccc', ?)", (uid,))
    conn.commit()


def test_cascade_delete_user_removes_encodings_and_tokens(db):
    conn = db.connect()
    conn.execute("INSERT INTO users(name) VALUES ('alice')")
    uid = conn.execute("SELECT id FROM users WHERE name='alice'").fetchone()[0]
    conn.execute("INSERT INTO face_encodings(user_id, embedding, sample_idx) VALUES (?, ?, 0)",
                 (uid, b"x" * 512))
    conn.execute("INSERT INTO qr_tokens(token, user_id) VALUES ('aaa', ?)", (uid,))
    conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM face_encodings").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM qr_tokens").fetchone()[0] == 0


def test_event_user_id_set_null_on_user_delete(db):
    conn = db.connect()
    conn.execute("INSERT INTO users(name) VALUES ('alice')")
    uid = conn.execute("SELECT id FROM users WHERE name='alice'").fetchone()[0]
    conn.execute("INSERT INTO events(method, user_id, granted) VALUES ('face', ?, 1)", (uid,))
    conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit()
    rows = list(conn.execute("SELECT user_id FROM events"))
    assert rows == [(None,)]


def test_insert_and_list_users(db):
    db.insert_user("alice")
    db.insert_user("bob")
    users = db.list_users()
    names = [r[1] for r in users]
    assert names == ["alice", "bob"]


def test_get_user_id_by_name(db):
    uid = db.insert_user("alice")
    assert db.get_user_id_by_name("alice") == uid
    assert db.get_user_id_by_name("nobody") is None


def test_insert_face_encoding_and_load_all(db):
    uid = db.insert_user("alice")
    db.insert_face_encoding(uid, b"x" * 512, 0)
    db.insert_face_encoding(uid, b"y" * 512, 1)
    rows = db.load_all_face_encodings()
    assert len(rows) == 2
    assert all(uid_loaded == uid for uid_loaded, _ in rows)


def test_revoke_and_rotate_qr(db):
    uid = db.insert_user("alice")
    db.insert_qr_token("aaa", uid)
    assert db.load_active_qr_tokens() == {"aaa": uid}
    n = db.revoke_active_qr(uid)
    assert n == 1
    assert db.load_active_qr_tokens() == {}
    db.insert_qr_token("bbb", uid)
    assert db.load_active_qr_tokens() == {"bbb": uid}


def test_insert_event_and_recent(db):
    db.insert_user("alice")
    uid = db.get_user_id_by_name("alice")
    eid = db.insert_event("face", uid, True, detail='{"distance":0.4}')
    assert eid > 0
    rows = db.recent_events()
    assert len(rows) == 1
    assert rows[0][2] == "face"             # method
    assert rows[0][4] == "alice"            # joined name


def test_update_event_clip(db):
    eid = db.insert_event("manual_open", None, True)
    db.update_event_clip(eid, "clips/42.mp4")
    rows = db.recent_events()
    assert rows[0][7] == "clips/42.mp4"
    db.update_event_clip(eid, None)
    rows = db.recent_events()
    assert rows[0][7] is None


def test_recent_events_filter_method(tmp_data_dir):
    db = Database(tmp_data_dir / "f.db"); db.migrate()
    db.insert_user("alice"); uid = db.get_user_id_by_name("alice")
    db.insert_event("face", uid, True)
    db.insert_event("qr", uid, True)
    db.insert_event("rfid", uid, True)
    rows = db.recent_events(method=["face", "qr"])
    methods = [r[2] for r in rows]
    assert sorted(methods) == ["face", "qr"]


def test_recent_events_filter_granted(tmp_data_dir):
    db = Database(tmp_data_dir / "g.db"); db.migrate()
    db.insert_event("face", None, True)
    db.insert_event("face", None, False)
    granted = db.recent_events(granted=1)
    denied = db.recent_events(granted=0)
    assert len(granted) == 1 and granted[0][5] == 1
    assert len(denied) == 1 and denied[0][5] == 0


def test_recent_events_filter_q(tmp_data_dir):
    db = Database(tmp_data_dir / "q.db"); db.migrate()
    db.insert_user("alice"); db.insert_user("bob")
    a, b = db.get_user_id_by_name("alice"), db.get_user_id_by_name("bob")
    db.insert_event("face", a, True)
    db.insert_event("face", b, True)
    rows = db.recent_events(q="ali")
    assert len(rows) == 1
    assert rows[0][4] == "alice"


def test_recent_events_before_id(tmp_data_dir):
    db = Database(tmp_data_dir / "p.db"); db.migrate()
    ids = [db.insert_event("face", None, True) for _ in range(5)]
    rows = db.recent_events(before_id=ids[3], limit=10)
    # before_id=ids[3] means strictly less than ids[3] -> ids[0], ids[1], ids[2]
    returned = sorted(r[0] for r in rows)
    assert returned == sorted(ids[:3])


def test_recent_events_after_id_combines_with_filter(tmp_data_dir):
    db = Database(tmp_data_dir / "c.db"); db.migrate()
    db.insert_user("alice"); a = db.get_user_id_by_name("alice")
    e1 = db.insert_event("face", a, True)
    e2 = db.insert_event("qr", a, True)
    e3 = db.insert_event("face", a, True)
    rows = db.recent_events(after_id=e1, method=["face"])
    assert {r[0] for r in rows} == {e3}


def test_recent_esp_log_orders_desc(tmp_data_dir):
    db = Database(tmp_data_dir / "l.db"); db.migrate()
    db.insert_esp_log("info", "boot", "first")
    db.insert_esp_log("warn", "audio", "second")
    db.insert_esp_log("info", "rfid", "third")
    rows = db.recent_esp_log(limit=10)
    msgs = [r[4] for r in rows]
    assert msgs == ["third", "second", "first"]


def test_recent_esp_log_after_id(tmp_data_dir):
    db = Database(tmp_data_dir / "la.db"); db.migrate()
    db.insert_esp_log("info", "a", "1")
    mid = db.insert_esp_log("info", "b", "2")
    db.insert_esp_log("info", "c", "3")
    rows = db.recent_esp_log(limit=10, after_id=mid)
    msgs = [r[4] for r in rows]
    assert msgs == ["3"]


def test_insert_esp_log_returns_id(tmp_data_dir):
    db = Database(tmp_data_dir / "i.db"); db.migrate()
    rid = db.insert_esp_log("info", "tag", "msg")
    assert isinstance(rid, int) and rid > 0


def test_count_events_today(tmp_data_dir):
    db = Database(tmp_data_dir / "ct.db"); db.migrate()
    # All events INSERTed with default ts=datetime('now') are "today"
    db.insert_event("face", None, True)
    db.insert_event("face", None, True)
    assert db.count_events_today() == 2


def test_db_uses_wal_and_normal_sync(tmp_path):
    """Pragmas must be applied right at connect() — before any migration —
    so that the very first writes go through WAL + NORMAL sync and won't
    instantly fail with SQLITE_BUSY under concurrent threads."""
    db = Database(tmp_path / "test.db")
    conn = db.connect()                                    # no migrate()
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
    sync = conn.execute("PRAGMA synchronous").fetchone()[0]
    # SQLite returns the integer; 1 = NORMAL
    assert sync in (1, "NORMAL", "normal")
    bt = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    assert bt >= 5000
    autock = conn.execute("PRAGMA wal_autocheckpoint").fetchone()[0]
    assert autock == 1000
