"""SQLite layer for smart_gate.

One connection per thread via threading.local. WAL + busy_timeout for low contention.
Migrations applied at startup; idempotent.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"

log = logging.getLogger(__name__)


class Database:
    def __init__(self, path: str | Path, migrations_dir: str | Path | None = None):
        self._path = Path(path)
        self._migrations_dir = Path(migrations_dir) if migrations_dir else _MIGRATIONS_DIR
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
            # Pragmas applied at connect() time — before any migration runs —
            # so very first writes already benefit from WAL + NORMAL sync and
            # concurrent writers don't immediately SQLITE_BUSY.
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA wal_autocheckpoint=1000")
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
        """Apply pending migrations in lexicographic order, skipping any
        whose numeric prefix is <= the current schema_version in _meta.

        Tracks the highest-applied prefix in _meta.schema_version. Files
        without a numeric prefix are ignored. executescript() implicitly
        wraps each .sql in its own transaction; the version bump that
        follows runs in autocommit and reflects a fully-applied file.
        """
        conn = self.connect()
        # _meta may not exist yet (fresh DB) — every migration file is
        # expected to either create it or rely on a prior one having done
        # so. Treat its absence as schema_version = 0.
        has_meta = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='_meta'"
        ).fetchone() is not None
        current = 0
        if has_meta:
            row = conn.execute(
                "SELECT value FROM _meta WHERE key='schema_version'"
            ).fetchone()
            if row:
                current = int(row[0])

        files = sorted(self._migrations_dir.glob("[0-9]*.sql"))
        for sql_file in files:
            try:
                num = int(sql_file.stem.split("_")[0])
            except ValueError:
                continue   # ignore non-numeric prefixes
            if num <= current:
                continue
            # executescript() issues an implicit COMMIT, so it can't be
            # nested inside self.transaction(). Each .sql file owns its
            # own atomicity; we just bump _meta after it succeeds.
            conn.executescript(sql_file.read_text())
            # Safety net: 0001 should create _meta, but make sure so the
            # version bump below doesn't crash on an unconventional file.
            conn.execute(
                "CREATE TABLE IF NOT EXISTS _meta "
                "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            conn.execute(
                "INSERT OR REPLACE INTO _meta(key, value) "
                "VALUES ('schema_version', ?)",
                (str(num),),
            )
            log.info("db: migrated to version %d via %s", num, sql_file.name)

    @contextmanager
    def transaction(self):
        """Explicit BEGIN IMMEDIATE … COMMIT/ROLLBACK around a write batch.

        Used to collapse multi-statement check-in paths (event row +
        last_seen update, or auto-enroll face_encoding insert) into a
        single fsync. ROLLBACK on exception keeps the row group atomic.
        """
        conn = self.connect()
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            conn.execute("ROLLBACK")
            raise
        else:
            conn.execute("COMMIT")

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
        # Inside an explicit transaction() block the outer COMMIT owns the
        # fsync — skip per-call commit so the batch collapses into 1 fsync.
        if not conn.in_transaction:
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
        # Inside an explicit transaction() block the outer COMMIT owns the
        # fsync — skip per-call commit so the batch collapses into 1 fsync.
        if not conn.in_transaction:
            conn.commit()
        return cur.lastrowid

    def update_event_clip(self, event_id: int, clip_path: str | None) -> None:
        conn = self.connect()
        conn.execute("UPDATE events SET clip_path=? WHERE id=?", (clip_path, event_id))
        conn.commit()

    def recent_events(self, limit: int = 50, after_id: int = 0,
                      before_id: int | None = None,
                      method: list[str] | None = None,
                      granted: int | None = None,
                      q: str | None = None,
                      since: str | None = None) -> list[tuple]:
        """Recent events with optional filters; all AND-combined.

        method is a list OR'd. q is case-insensitive LIKE on users.name.
        since is an ISO timestamp; rows with ts >= since. before_id is for
        keyset pagination of older rows.
        """
        where = ["e.id > ?"]
        params: list = [after_id]
        if before_id is not None:
            where.append("e.id < ?"); params.append(before_id)
        if method:
            where.append("e.method IN (" + ",".join(["?"] * len(method)) + ")")
            params.extend(method)
        if granted is not None:
            where.append("e.granted = ?"); params.append(int(granted))
        if q:
            where.append("u.name LIKE ?"); params.append(f"%{q}%")
        if since:
            where.append("e.ts >= ?"); params.append(since)
        params.append(limit)
        conn = self.connect()
        return list(conn.execute(
            "SELECT e.id, e.ts, e.method, e.user_id, u.name, e.granted, "
            "e.detail, e.clip_path "
            "FROM events e LEFT JOIN users u ON u.id = e.user_id "
            f"WHERE {' AND '.join(where)} "
            "ORDER BY e.id DESC LIMIT ?",
            params,
        ))

    def last_grant_event(self) -> dict | None:
        """Most recent granted event as {ts, name}, or None."""
        conn = self.connect()
        row = conn.execute(
            "SELECT e.ts, u.name FROM events e "
            "LEFT JOIN users u ON u.id = e.user_id "
            "WHERE e.granted = 1 "
            "ORDER BY e.id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return {"ts": row[0], "name": row[1] or "—"}

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

    def insert_esp_log(self, lvl: str, tag: str | None, msg: str) -> int:
        conn = self.connect()
        cur = conn.execute(
            "INSERT INTO esp_log(lvl, tag, msg) VALUES (?, ?, ?)",
            (lvl, tag, msg),
        )
        conn.commit()
        return cur.lastrowid

    def insert_esp_log_many(self, rows) -> None:
        """Batched INSERT for esp_log; rows is iterable of (lvl, tag, msg).

        Used by EspLogWriter to coalesce up to 1 second of high-frequency
        ESP log lines into a single fsync. Wrapped in transaction() so the
        whole batch shares one COMMIT.
        """
        conn = self.connect()
        with self.transaction():
            conn.executemany(
                "INSERT INTO esp_log(lvl, tag, msg) VALUES (?, ?, ?)",
                rows,
            )

    def recent_esp_log(self, limit: int = 100, after_id: int = 0) -> list[tuple]:
        conn = self.connect()
        return list(conn.execute(
            "SELECT id, ts, lvl, tag, msg FROM esp_log "
            "WHERE id > ? ORDER BY id DESC LIMIT ?",
            (after_id, limit),
        ))

    def count_events_today(self) -> int:
        conn = self.connect()
        return conn.execute(
            "SELECT COUNT(*) FROM events "
            "WHERE ts >= datetime('now','start of day')"
        ).fetchone()[0]
