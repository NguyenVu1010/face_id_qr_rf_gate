"""Flask web admin.

Factory pattern (`create_app`) so tests pass mocks for db/hub/uart/matcher/overlay.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from pathlib import Path

import numpy as np
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

_USER_NAME_RE = re.compile(r"^user_\d+$")


def create_app(*, db, hub, uart, data_dir: Path, start_time: float | None = None,
               matcher=None, overlay=None, reload_event=None,
               cv2_module=None) -> Flask:
    start_time = start_time or time.monotonic()
    data_dir = Path(data_dir)
    qr_dir = data_dir / "qr"
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
        """MJPEG with face-detection bbox overlay drawn from OverlayState."""
        def gen():
            try:
                while True:
                    jpg = _annotated_jpeg(hub, overlay, cv2_module)
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

    @app.route("/qr/<name>.png")
    def qr_image(name: str):
        # Defensive: only allow alphanumeric/underscore names.
        if not re.match(r"^[A-Za-z0-9_\-]+$", name):
            abort(400)
        if not (qr_dir / f"{name}.png").exists():
            abort(404)
        # ?download=1 forces browser to save instead of inline display.
        as_attachment = request.args.get("download") in ("1", "true", "yes")
        return send_from_directory(
            qr_dir, f"{name}.png", mimetype="image/png",
            as_attachment=as_attachment,
            download_name=f"smart_gate_{name}.png" if as_attachment else None,
        )

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

    @app.route("/api/enroll", methods=["POST"])
    def enroll():
        """Create a new user_NNN with a QR token. Face binds automatically
        on first QR scan or RFID swipe matching this user.

        Body (JSON, optional): {"face_capture": false, "samples": 3}
          face_capture=false (default): just creates user + QR, no face.
            User holds the QR up to the webcam and the daemon auto-enrolls
            the visible face under this user.
          face_capture=true: captures N face samples from the live stream
            immediately, like the CLI enroll. Useful when no QR/RFID flow
            is available.

        Returns: {"ok": true, "name": "user_001", "id": N,
                  "captured": M, "qr_url": "..."}
        """
        body = request.get_json(silent=True) or {}
        face_capture = bool(body.get("face_capture", False))
        n_samples = max(1, min(int(body.get("samples", 3)), 10))
        delay_s = max(0.2, min(float(body.get("delay_s", 0.8)), 3.0))

        name = _allocate_user_name(db)

        encs = []
        if face_capture:
            try:
                encs = _flask_capture_face_samples(hub, n_samples, delay_s,
                                                  cv2_module)
            except RuntimeError as e:
                return jsonify({"error": str(e)}), 503
            if len(encs) < n_samples:
                return jsonify({
                    "error": f"only captured {len(encs)}/{n_samples} "
                             "samples — face not detected in some frames",
                    "captured": len(encs),
                }), 400

        from smart_gate.cli import qr as qr_mod
        uid = db.insert_user(name)
        for i, enc in enumerate(encs):
            db.insert_face_encoding(uid, enc.astype("float32").tobytes(), i)
        _ = qr_mod.issue_initial(db, name, qr_dir)

        if reload_event is not None:
            reload_event.set()
        elif matcher is not None:
            matcher.reload(db)

        log.info("created user %s (id=%d, %d face samples; face_capture=%s)",
                 name, uid, len(encs), face_capture)
        return jsonify({
            "ok": True,
            "name": name,
            "id": uid,
            "captured": len(encs),
            "qr_url": f"/qr/{name}.png",
            "face_capture": face_capture,
        })

    @app.route("/healthz")
    def healthz():
        expected = {"cap", "detect", "rec", "bus-consumer", "flask",
                    "cleanup", "uart-rx", "uart-tx", "uart-hb"}
        active = {t.name for t in threading.enumerate()}
        last_frame_ago = None
        last_ts = getattr(hub, "_last_publish_mono", None)
        if last_ts is not None:
            last_frame_ago = max(0.0, time.monotonic() - last_ts)
        n_users = len(db.list_users()) if hasattr(db, "list_users") else None
        return jsonify({
            "uptime_s": int(time.monotonic() - start_time),
            "link_alive": bool(uart.link_alive()),
            "last_frame_ago_s": last_frame_ago,
            "threads_ok": expected.issubset(active),
            "enrolled_users": n_users,
        })

    return app


def _allocate_user_name(db) -> str:
    """Generate next user_NNN id where NNN is one greater than the current max."""
    rows = db.list_users()
    nums = []
    for row in rows:
        name = row[1]
        if _USER_NAME_RE.match(name):
            try:
                nums.append(int(name.split("_")[1]))
            except (IndexError, ValueError):
                pass
    nxt = (max(nums) + 1) if nums else 1
    return f"user_{nxt:03d}"


def _flask_capture_face_samples(hub, n_samples, delay_s, cv2_module=None):
    """Block-grab N BGR frames from FrameHub, return list of 128-d encodings.

    Each sample: poll FrameHub up to 8s for a frame containing a detectable
    face; if found, encode and append. If no face within deadline, skip that
    slot. Caller decides what to do with partial results.
    """
    if cv2_module is None:
        import cv2 as cv2_module
    import face_recognition as fr

    encs: list[np.ndarray] = []
    for i in range(n_samples):
        if i > 0:
            time.sleep(delay_s)
        deadline = time.monotonic() + 8.0
        enc = None
        while time.monotonic() < deadline:
            bgr = hub.wait_bgr(timeout=2.0)
            if bgr is None:
                continue
            enc = _encode_face(bgr, cv2_module, fr)
            if enc is not None:
                break
        if enc is not None:
            encs.append(enc)
    return encs


def _encode_face(bgr, cv2_module, fr):
    rgb = cv2_module.cvtColor(bgr, cv2_module.COLOR_BGR2RGB)
    locations = fr.face_locations(rgb, model="hog", number_of_times_to_upsample=1)
    if not locations:
        return None
    locations.sort(key=lambda l: (l[2] - l[0]) * (l[1] - l[3]), reverse=True)
    encs = fr.face_encodings(rgb, known_face_locations=locations[:1],
                             num_jitters=1)
    return encs[0] if encs else None


def _annotated_jpeg(hub, overlay, cv2_module=None):
    """Return a JPEG (bytes) with the latest BGR frame + bbox overlay drawn.

    If cv2 is unavailable, falls back to raw cap-thread JPEG (no overlay).
    """
    if cv2_module is None:
        try:
            import cv2 as cv2_module
        except ImportError:
            jpg = hub.wait_jpeg(timeout=2.0)
            return jpg

    bgr = hub.wait_bgr(timeout=2.0)
    if bgr is None:
        return None

    annotated = bgr.copy()
    info = overlay.get_if_fresh() if overlay is not None else None
    if info is not None and info.bbox is not None:
        x, y, w, h = info.bbox
        cv2_module.rectangle(annotated, (x, y), (x + w, y + h), info.color, 2)
        if info.label:
            cv2_module.putText(annotated, info.label, (x, max(20, y - 8)),
                               cv2_module.FONT_HERSHEY_SIMPLEX,
                               0.7, info.color, 2)
    ok, buf = cv2_module.imencode(".jpg", annotated,
                                  [cv2_module.IMWRITE_JPEG_QUALITY, 75])
    return buf.tobytes() if ok else None


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
