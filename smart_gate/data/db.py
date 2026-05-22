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
