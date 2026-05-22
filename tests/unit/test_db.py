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
