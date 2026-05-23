"""Two-factor check-in state.

Each successful check-in requires BOTH:
1. A face detected and matched (or unmatched, in which case auto-enroll runs).
2. A credential scan (QR token or RFID UID) within `ttl_s` seconds.

Either order is supported — whichever side arrives second triggers the
check-in. The state holds:
- pending_face: latest face seen (embedding + matched user_id or None)
- pending_grant: latest valid credential (user_id + source)

set_face_and_try_match / set_grant_and_try_match update the corresponding
slot and atomically return a `CheckInPair` if BOTH slots are fresh. On a
returned pair, both slots are cleared so a single hardware action can't
double-trigger.

Anything that doesn't pair up is silently held until TTL — no event is
written. Face seen alone never produces a DB row; credential alone never
produces a DB row.
"""
from __future__ import annotations

import dataclasses
import threading
import time

import numpy as np


@dataclasses.dataclass(frozen=True)
class PendingFace:
    embedding: np.ndarray
    matched_user_id: int | None
    distance: float
    ts_mono: float


@dataclasses.dataclass(frozen=True)
class PendingGrant:
    user_id: int
    source: str           # 'qr' or 'rfid'
    ts_mono: float


@dataclasses.dataclass(frozen=True)
class CheckInPair:
    face_embedding: np.ndarray
    face_matched_user_id: int | None
    face_distance: float
    grant_user_id: int
    grant_source: str


class TwoFactorState:
    """Two-factor pairing with consumption cooldown.

    The user almost always keeps face + credential in frame for several
    seconds after the gate opens. Without a cooldown, the detector fires
    a fresh CheckInEvent on EVERY camera frame (10-15 fps) for the same
    logical scan, spamming auto-enroll inserts and bus events.

    `consumption_cooldown_s` (default 5s) suppresses pair consumption
    after a successful consume. Slots can still be updated (face moves,
    grant changes) but `_try_consume_locked` returns None until the
    cooldown elapses. Effectively: one CheckInEvent per visit.
    """

    def __init__(self, ttl_s: float = 4.0,
                 consumption_cooldown_s: float = 5.0):
        self._lock = threading.Lock()
        self._face: PendingFace | None = None
        self._grant: PendingGrant | None = None
        self._ttl_s = ttl_s
        self._consumption_cooldown_s = consumption_cooldown_s
        self._last_consumed_mono: float = -1e9

    # -------- writers --------

    def set_face_and_try_match(self, embedding: np.ndarray,
                               matched_user_id: int | None,
                               distance: float) -> CheckInPair | None:
        with self._lock:
            self._face = PendingFace(
                embedding=embedding,
                matched_user_id=matched_user_id,
                distance=distance,
                ts_mono=time.monotonic(),
            )
            return self._try_consume_locked()

    def set_grant_and_try_match(self, user_id: int,
                                source: str) -> CheckInPair | None:
        with self._lock:
            self._grant = PendingGrant(
                user_id=user_id, source=source, ts_mono=time.monotonic(),
            )
            return self._try_consume_locked()

    def clear(self) -> None:
        with self._lock:
            self._face = None
            self._grant = None

    def reset_cooldown(self) -> None:
        """Force the next pair to consume immediately (for tests / admin)."""
        with self._lock:
            self._last_consumed_mono = -1e9

    # -------- read-only --------

    def has_fresh_grant(self) -> bool:
        with self._lock:
            g = self._grant
        if g is None:
            return False
        return (time.monotonic() - g.ts_mono) <= self._ttl_s

    def has_fresh_face(self) -> bool:
        with self._lock:
            f = self._face
        if f is None:
            return False
        return (time.monotonic() - f.ts_mono) <= self._ttl_s

    # -------- internal --------

    def _try_consume_locked(self) -> CheckInPair | None:
        f, g = self._face, self._grant
        if f is None or g is None:
            return None
        now = time.monotonic()
        if now - f.ts_mono > self._ttl_s or now - g.ts_mono > self._ttl_s:
            return None
        # Consumption cooldown — same logical check-in can't fire repeatedly
        # while user keeps both face and credential in frame.
        if now - self._last_consumed_mono < self._consumption_cooldown_s:
            return None
        pair = CheckInPair(
            face_embedding=f.embedding,
            face_matched_user_id=f.matched_user_id,
            face_distance=f.distance,
            grant_user_id=g.user_id,
            grant_source=g.source,
        )
        self._face = None
        self._grant = None
        self._last_consumed_mono = now
        return pair
