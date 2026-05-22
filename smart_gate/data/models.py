"""Dataclasses representing DB rows."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class User:
    id: int
    name: str
    created_at: str
    last_seen: str | None = None
    note: str | None = None


@dataclass
class FaceEncoding:
    id: int
    user_id: int
    embedding: bytes        # 128 × float32 = 512 bytes
    sample_idx: int


@dataclass
class QrToken:
    token: str
    user_id: int
    created_at: str
    revoked_at: str | None = None


@dataclass
class Event:
    id: int
    ts: str
    method: str
    user_id: int | None
    granted: bool
    detail: str | None = None
    clip_path: str | None = None
