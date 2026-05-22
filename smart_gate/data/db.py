"""SQLite layer for smart_gate.

One connection per thread via threading.local. WAL + busy_timeout for low contention.
Migrations applied at startup; idempotent.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class Database:
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._tls = threading.local()

    def connect(self) -> sqlite3.Connection:
        conn = getattr(self._tls, "conn", None)
        if conn is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(
                str(self._path),
                detect_types=sqlite3.PARSE_DECLTYPES,
                isolation_level=None,           # autocommit; we use explicit transactions
                check_same_thread=False,
            )
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=5000")
            self._tls.conn = conn
        return conn

    def close(self) -> None:
        conn = getattr(self._tls, "conn", None)
        if conn is not None:
            conn.close()
            self._tls.conn = None

    def migrate(self) -> None:
        conn = self.connect()
        files = sorted(_MIGRATIONS_DIR.glob("[0-9]*.sql"))
        for sql_file in files:
            sql = sql_file.read_text()
            conn.executescript(sql)
        conn.commit()

    # ---- Users ----

    def insert_user(self, name: str, note: str | None = None) -> int:
        conn = self.connect()
        cur = conn.execute("INSERT INTO users(name, note) VALUES (?, ?)", (name, note))
        conn.commit()
        return cur.lastrowid

    def get_user_id_by_name(self, name: str) -> int | None:
        conn = self.connect()
        row = conn.execute("SELECT id FROM users WHERE name=?", (name,)).fetchone()
        return row[0] if row else None

    def list_users(self) -> list[tuple]:
        conn = self.connect()
        return list(conn.execute("""
            SELECT u.id, u.name, u.created_at, u.last_seen,
                   (SELECT COUNT(*) FROM face_encodings f WHERE f.user_id=u.id) AS n_enc,
                   (SELECT COUNT(*) FROM qr_tokens q
                    WHERE q.user_id=u.id AND q.revoked_at IS NULL) AS n_qr
            FROM users u
            ORDER BY u.id
        """))

    def delete_user(self, name: str) -> bool:
        conn = self.connect()
        cur = conn.execute("DELETE FROM users WHERE name=?", (name,))
        conn.commit()
        return cur.rowcount > 0

    def touch_last_seen(self, user_id: int) -> None:
        conn = self.connect()
        conn.execute("UPDATE users SET last_seen=datetime('now') WHERE id=?", (user_id,))
        conn.commit()

    # ---- Face encodings ----

    def insert_face_encoding(self, user_id: int, embedding: bytes, sample_idx: int) -> None:
        conn = self.connect()
        conn.execute(
            "INSERT INTO face_encodings(user_id, embedding, sample_idx) VALUES (?, ?, ?)",
            (user_id, embedding, sample_idx),
        )
        conn.commit()

    def load_all_face_encodings(self) -> list[tuple[int, bytes]]:
        conn = self.connect()
        return list(conn.execute("SELECT user_id, embedding FROM face_encodings"))

    # ---- QR tokens ----

    def insert_qr_token(self, token: str, user_id: int) -> None:
        conn = self.connect()
        conn.execute(
            "INSERT INTO qr_tokens(token, user_id) VALUES (?, ?)", (token, user_id),
        )
        conn.commit()

    def revoke_active_qr(self, user_id: int) -> int:
        conn = self.connect()
        cur = conn.execute(
            "UPDATE qr_tokens SET revoked_at=datetime('now') "
            "WHERE user_id=? AND revoked_at IS NULL", (user_id,)
        )
        conn.commit()
        return cur.rowcount

    def load_active_qr_tokens(self) -> dict[str, int]:
        conn = self.connect()
        return {token: uid for token, uid in conn.execute(
            "SELECT token, user_id FROM qr_tokens WHERE revoked_at IS NULL"
        )}

    # ---- Events ----

    def insert_event(self, method: str, user_id: int | None,
                     granted: bool, detail: str | None = None) -> int:
        conn = self.connect()
        cur = conn.execute(
            "INSERT INTO events(method, user_id, granted, detail) VALUES (?, ?, ?, ?)",
            (method, user_id, 1 if granted else 0, detail),
        )
        conn.commit()
        return cur.lastrowid

    def update_event_clip(self, event_id: int, clip_path: str | None) -> None:
        conn = self.connect()
        conn.execute("UPDATE events SET clip_path=? WHERE id=?", (clip_path, event_id))
        conn.commit()

    def recent_events(self, limit: int = 50, after_id: int = 0) -> list[tuple]:
        conn = self.connect()
        return list(conn.execute("""
            SELECT e.id, e.ts, e.method, e.user_id, u.name, e.granted, e.detail, e.clip_path
            FROM events e LEFT JOIN users u ON u.id = e.user_id
            WHERE e.id > ?
            ORDER BY e.id DESC
            LIMIT ?
        """, (after_id, limit)))

    def get_event_clip(self, event_id: int) -> str | None:
        conn = self.connect()
        row = conn.execute("SELECT clip_path FROM events WHERE id=?", (event_id,)).fetchone()
        if row is None:
            return None
        return row[0]

    def events_for_cleanup(self) -> list[tuple]:
        conn = self.connect()
        return list(conn.execute(
            "SELECT id, ts, clip_path FROM events WHERE clip_path IS NOT NULL ORDER BY ts ASC"
        ))

    # ---- ESP log ----

    def insert_esp_log(self, lvl: str, tag: str | None, msg: str) -> None:
        conn = self.connect()
        conn.execute("INSERT INTO esp_log(lvl, tag, msg) VALUES (?, ?, ?)", (lvl, tag, msg))
        conn.commit()
