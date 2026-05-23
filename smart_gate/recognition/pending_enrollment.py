"""Shared 'pending face' state used by the auto-enroll flow.

Detector writes the latest face embedding here every frame, tagged with
whether it matched any user. The bus consumer reads it when an RFID
swipe or QR scan succeeds: if a recent unmatched embedding is present,
that embedding is auto-enrolled under the user_id of the credential.
Next time the same face appears, it shows as green with the user's name.

Stale entries (older than `ttl_s`) are ignored so an auto-enroll only
happens when the credential and the face actually co-occur.
"""
from __future__ import annotations

import dataclasses
import threading
import time

import numpy as np


@dataclasses.dataclass(frozen=True)
class PendingFace:
    embedding: np.ndarray       # float32[128]
    matched: bool               # True ⇒ already in DB
    user_id: int | None         # set when matched
    ts_mono: float


class PendingEnrollment:
    def __init__(self):
        self._lock = threading.Lock()
        self._face: PendingFace | None = None

    def set(self, embedding: np.ndarray, matched: bool,
            user_id: int | None = None) -> None:
        with self._lock:
            self._face = PendingFace(
                embedding=embedding,
                matched=matched,
                user_id=user_id,
                ts_mono=time.monotonic(),
            )

    def clear(self) -> None:
        with self._lock:
            self._face = None

    def get_if_fresh(self, ttl_s: float = 3.0) -> PendingFace | None:
        with self._lock:
            f = self._face
        if f is None:
            return None
        if time.monotonic() - f.ts_mono > ttl_s:
            return None
        return f
