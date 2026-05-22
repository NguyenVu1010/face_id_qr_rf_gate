"""QR generation, rotation, revocation."""
from __future__ import annotations

import secrets
from pathlib import Path

import qrcode

from smart_gate.cli._signal import signal_daemon


def _new_token() -> str:
    return secrets.token_hex(16)


def _write_qr_png(token: str, name: str, qr_dir: Path) -> Path:
    qr_dir.mkdir(parents=True, exist_ok=True)
    out = qr_dir / f"{name}.png"
    img = qrcode.make(token)
    img.save(out)
    return out


def rotate(db, name: str, qr_dir: Path) -> Path:
    uid = db.get_user_id_by_name(name)
    if uid is None:
        raise SystemExit(f"user not found: {name}")
    db.revoke_active_qr(uid)
    token = _new_token()
    db.insert_qr_token(token, uid)
    path = _write_qr_png(token, name, qr_dir)
    signal_daemon()
    return path


def revoke(db, name: str) -> int:
    uid = db.get_user_id_by_name(name)
    if uid is None:
        raise SystemExit(f"user not found: {name}")
    n = db.revoke_active_qr(uid)
    signal_daemon()
    return n


def issue_initial(db, name: str, qr_dir: Path) -> Path:
    """Used by enroll: insert first token for a brand-new user."""
    uid = db.get_user_id_by_name(name)
    token = _new_token()
    db.insert_qr_token(token, uid)
    return _write_qr_png(token, name, qr_dir)
