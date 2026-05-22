"""In-memory matcher.

Holds face encodings + QR tokens loaded from SQLite. Reload on SIGUSR1
(triggered from main.py when CLI mutates DB).
"""
from __future__ import annotations

import threading
import numpy as np


class Matcher:
    def __init__(self, db):
        self._lock = threading.RLock()
        self._faces: list[tuple[int, np.ndarray]] = []
        self._qrs: dict[str, int] = {}
        self.reload(db)

    def reload(self, db) -> None:
        rows = db.load_all_face_encodings()
        faces = [
            (user_id, np.frombuffer(emb, dtype="float32").copy())
            for user_id, emb in rows
        ]
        qrs = db.load_active_qr_tokens()
        with self._lock:
            self._faces = faces
            self._qrs = qrs

    def match_face(self, probe: np.ndarray) -> tuple[int | None, float]:
        with self._lock:
            faces = self._faces
        if not faces:
            return None, float("inf")
        user_dists: dict[int, float] = {}
        for user_id, enc in faces:
            d = float(np.linalg.norm(probe - enc))
            cur = user_dists.get(user_id, float("inf"))
            if d < cur:
                user_dists[user_id] = d
        best_user, best_dist = None, float("inf")
        for user_id, d in user_dists.items():
            if d < best_dist:
                best_user, best_dist = user_id, d
        return best_user, best_dist

    def lookup_qr(self, token: str) -> int | None:
        with self._lock:
            return self._qrs.get(token)
