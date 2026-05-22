"""Flask web admin.

Factory pattern (`create_app`) so tests pass mocks for db/hub/uart.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from flask import (Flask, Response, abort, jsonify, render_template, request,
                   send_from_directory)

from smart_gate.link.uart_client import LinkDown, LinkTimeout

log = logging.getLogger(__name__)

_PLACEHOLDER_JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00" + b"\x10" * 64 +
    b"\xff\xc0\x00\x0b\x08\x00\x10\x00\x10\x01\x01\x11\x00"
    b"\xff\xc4\x00\x14\x00\x01\x00" + b"\x00" * 14 +
    b"\x05\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb\xa0\xff\xd9"
)


def create_app(*, db, hub, uart, data_dir: Path, start_time: float | None = None) -> Flask:
    start_time = start_time or time.monotonic()
    data_dir = Path(data_dir)
    app = Flask(__name__,
                template_folder=str(Path(__file__).parent / "templates"),
                static_folder=str(Path(__file__).parent / "static"))

    @app.route("/")
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/users")
    def users():
        return render_template("users.html", users=db.list_users())

    @app.route("/stream.mjpeg")
    def stream():
        def gen():
            try:
                while True:
                    jpg = hub.wait_jpeg(timeout=2.0)
                    if jpg is None:
                        jpg = _PLACEHOLDER_JPEG
                    yield (b"--FRAME\r\nContent-Type: image/jpeg\r\n"
                           b"Content-Length: " + str(len(jpg)).encode() + b"\r\n\r\n"
                           + jpg + b"\r\n")
            except (GeneratorExit, OSError):
                return
        return Response(gen(),
                        mimetype="multipart/x-mixed-replace; boundary=FRAME")

    @app.route("/events.json")
    def events_json():
        after_id = int(request.args.get("after_id", 0))
        rows = db.recent_events(limit=50, after_id=after_id)
        fmt = request.args.get("format", "json")
        if fmt == "html":
            return render_template_string_events(rows)
        return jsonify([
            {"id": r[0], "ts": r[1], "method": r[2], "user_id": r[3],
             "user_name": r[4], "granted": bool(r[5]),
             "detail": r[6], "clip_path": r[7]} for r in rows
        ])

    @app.route("/clips/<int:event_id>.mp4")
    def clip(event_id: int):
        clip_path = db.get_event_clip(event_id)
        if clip_path is None:
            abort(404)
        return send_from_directory(data_dir, clip_path, mimetype="video/mp4")

    @app.route("/api/gate/open", methods=["POST"])
    def gate_open():
        return _gate_action("open", "manual_open")

    @app.route("/api/gate/close", methods=["POST"])
    def gate_close():
        return _gate_action("close", "manual_close")

    def _gate_action(verb: str, method: str):
        try:
            uart.send_cmd(verb, {"user": "admin", "reason": "manual"}
                          if verb == "open" else None, timeout=2.0)
        except (LinkDown, LinkTimeout) as e:
            return jsonify({"error": str(e)}), 503
        db.insert_event(method, None, True)
        return jsonify({"ok": True})

    @app.route("/healthz")
    def healthz():
        import threading
        expected = {"cap", "detect", "rec", "bus-consumer", "flask",
                    "cleanup", "uart-rx", "uart-tx", "uart-hb"}
        active = {t.name for t in threading.enumerate()}
        last_frame_ago = None
        last_ts = getattr(hub, "_last_publish_mono", None)
        if last_ts is not None:
            last_frame_ago = max(0.0, time.monotonic() - last_ts)
        return jsonify({
            "uptime_s": int(time.monotonic() - start_time),
            "link_alive": bool(uart.link_alive()),
            "last_frame_ago_s": last_frame_ago,
            "threads_ok": expected.issubset(active),
        })

    return app


def render_template_string_events(rows):
    """Render the events.json HTMX fragment without using a separate template."""
    parts = []
    for r in rows:
        ev_id, ts, method, _uid, name, granted, _detail, clip = r
        ok = "✓" if granted else "✗"
        clip_link = f'<a href="/clips/{ev_id}.mp4">▶</a>' if clip else "-"
        name = name or "-"
        parts.append(
            f"<tr><td>{ts}</td><td>{method}</td><td>{name}</td>"
            f"<td>{ok}</td><td>{clip_link}</td></tr>"
        )
    return "".join(parts)
