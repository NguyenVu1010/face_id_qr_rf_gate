"""RFID-only auto-enroll pairing.

Holds the most recent unmatched face and the most recent RFID grant. When
both are fresh (within `ttl_s`) AND the face is currently unmatched in the
encoding DB, returns an `EnrollCandidate` so the daemon can insert a new
face encoding under the RFID grant's user_id.

This is NOT the gate-open path — gate-open happens independently via the
face / QR / RFID channel routers in detector.py and main.py. This module
only handles the "tap card, look at camera → system learns face" UX.

QR grants are silently ignored (per 2026-06-12 design decision).
"""
from __future__ import annotations

import dataclasses
import threading
import time
from typing import Optional

import numpy as np


@dataclasses.dataclass(frozen=True)
class _PendingFace:
    embedding: np.ndarray
    matched_user_id: Optional[int]
    distance: float
    ts_mono: float


@dataclasses.dataclass(frozen=True)
class _PendingGrant:
    user_id: int
    ts_mono: float


@dataclasses.dataclass(frozen=True)
class EnrollCandidate:
    embedding: np.ndarray
    grant_user_id: int
    face_distance: float


class AutoEnrollPairState:
    def __init__(self, ttl_s: float = 4.0):
        self._ttl_s = ttl_s
        self._lock = threading.Lock()
        self._face: Optional[_PendingFace] = None
        self._grant: Optional[_PendingGrant] = None

    def set_face_seen(self, embedding: np.ndarray,
                      matched_user_id: Optional[int],
                      distance: float) -> Optional[EnrollCandidate]:
        with self._lock:
            self._face = _PendingFace(
                embedding=embedding,
                matched_user_id=matched_user_id,
                distance=distance,
                ts_mono=time.monotonic(),
            )
            return self._try_pair_locked()

    def set_grant_and_wait_for_face(self, user_id: int, source: str
                                    ) -> Optional[EnrollCandidate]:
        if source != "rfid":
            return None
        with self._lock:
            self._grant = _PendingGrant(user_id=user_id,
                                        ts_mono=time.monotonic())
            return self._try_pair_locked()

    def clear(self) -> None:
        with self._lock:
            self._face = None
            self._grant = None

    def _try_pair_locked(self) -> Optional[EnrollCandidate]:
        f, g = self._face, self._grant
        if f is None or g is None:
            return None
        now = time.monotonic()
        if now - f.ts_mono > self._ttl_s or now - g.ts_mono > self._ttl_s:
            return None
        if f.matched_user_id is not None:
            # Face already enrolled — don't double-enroll. Don't clear slots
            # either; a fresh unmatched face could arrive within the window.
            return None
        cand = EnrollCandidate(
            embedding=f.embedding,
            grant_user_id=g.user_id,
            face_distance=f.distance,
        )
        # Consume both slots so the same physical action doesn't enroll twice.
        self._face = None
        self._grant = None
        return cand
