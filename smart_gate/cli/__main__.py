"""argparse-based dispatcher: python -m smart_gate.cli <subcommand>."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from smart_gate.config import load_config
from smart_gate.data.db import Database
from smart_gate.cli import enroll as enroll_mod
from smart_gate.cli import qr as qr_mod
from smart_gate.cli import users as users_mod
from smart_gate.cli import events as events_mod


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="smart_gate.cli")
    p.add_argument("--config", default="/etc/smart-gate/config.toml")
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("enroll")
    e.add_argument("--name", required=True)
    e.add_argument("--samples", type=int, default=5)
    e.add_argument("--camera", type=int, default=0,
                   help="camera index; ignored if config.video.camera_device is set")
    e.add_argument("--headless", action="store_true",
                   help="no preview window; auto-capture every --delay-s seconds")
    e.add_argument("--delay-s", type=float, default=1.5,
                   help="seconds between samples in headless mode (default 1.5)")

    u = sub.add_parser("users")
    u_sub = u.add_subparsers(dest="users_cmd", required=True)
    u_sub.add_parser("list")
    ud = u_sub.add_parser("delete")
    ud.add_argument("--name", required=True)

    q = sub.add_parser("qr")
    q_sub = q.add_subparsers(dest="qr_cmd", required=True)
    qr_rot = q_sub.add_parser("rotate"); qr_rot.add_argument("--name", required=True)
    qr_rev = q_sub.add_parser("revoke"); qr_rev.add_argument("--name", required=True)

    ev = sub.add_parser("events")
    ev_sub = ev.add_subparsers(dest="events_cmd", required=True)
    ev_tail = ev_sub.add_parser("tail"); ev_tail.add_argument("-n", type=int, default=20)

    sub.add_parser("db").add_subparsers(dest="db_cmd", required=True).add_parser("migrate")

    args = p.parse_args(argv)
    logging.basicConfig(level="INFO", format="%(levelname)s: %(message)s")

    cfg = load_config(args.config)
    db_path = Path(cfg.paths.data_dir) / "smart_gate.db"
    qr_dir = Path(cfg.paths.data_dir) / "qr"
    db = Database(db_path)
    db.migrate()

    if args.cmd == "enroll":
        # Prefer the config's camera_device (stable /dev path from udev)
        # over --camera. --camera is still accepted as an override.
        camera_src = cfg.video.camera_device or args.camera
        enroll_mod.enroll(db, args.name, qr_dir, args.samples, camera_src,
                          headless=args.headless, delay_s=args.delay_s)
    elif args.cmd == "users" and args.users_cmd == "list":
        users_mod.list_users(db)
    elif args.cmd == "users" and args.users_cmd == "delete":
        users_mod.delete_user(db, args.name)
    elif args.cmd == "qr" and args.qr_cmd == "rotate":
        path = qr_mod.rotate(db, args.name, qr_dir)
        print(f"new QR: {path}")
    elif args.cmd == "qr" and args.qr_cmd == "revoke":
        n = qr_mod.revoke(db, args.name)
        print(f"revoked {n} token(s)")
    elif args.cmd == "events" and args.events_cmd == "tail":
        events_mod.tail(db, args.n)
    elif args.cmd == "db":
        print("migration applied")
    else:
        p.error("unknown command")
    return 0


if __name__ == "__main__":
    sys.exit(main())
