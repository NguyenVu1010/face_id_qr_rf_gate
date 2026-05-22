"""User list / delete subcommands."""
from __future__ import annotations

from smart_gate.cli._signal import signal_daemon


def list_users(db) -> None:
    print(f"{'id':>3}  {'name':<20} {'created':<19} {'last_seen':<19} {'#enc':>4} {'qr':>3}")
    for row in db.list_users():
        ev_id, name, created, last_seen, n_enc, n_qr = row
        last_seen = last_seen or "-"
        print(f"{ev_id:>3}  {name:<20} {created:<19} {last_seen:<19} {n_enc:>4} {n_qr:>3}")


def delete_user(db, name: str) -> None:
    if not db.delete_user(name):
        raise SystemExit(f"user not found: {name}")
    signal_daemon()
    print(f"deleted {name}")
