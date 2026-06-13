"""Flask web admin.

Factory pattern (`create_app`) so tests pass mocks for db/hub/uart/matcher/overlay.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from pathlib import Path

import json

import numpy as np
from flask import (Flask, Response, abort, jsonify, render_template, request,
                   send_from_directory, stream_with_context)

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

# ISO 14443 UIDs come in 4/7/10 bytes → 8/14/20 hex chars. Accept the full
# 8-20 range so 7-byte Mifare Ultralight / DESFire cards also work.
_UID_RE = re.compile(r"^[0-9A-Fa-f]{8,20}$")


def _int_param(name: str, default: int, lo: int, hi: int) -> int:
    """Parse `request.args[name]` as int with [lo, hi] bounds.

    Returns HTTP 400 on non-numeric input *or* values below ``lo``
    (negative limits are a known SQLite exfil vector: SQLite treats
    ``LIMIT -1`` as "no limit" and would dump the entire table).
    Values above ``hi`` are clamped down — honest clients asking for
    a "big" page still get the max page rather than a confusing 400.
    """
    raw = request.args.get(name, default)
    try:
        v = int(raw)
    except (TypeError, ValueError):
        abort(400, f"bad {name}")
    if v < lo:
        abort(400, f"bad {name}")
    return min(v, hi)


def _emit_audit(esp_log_bus, lvl: str, tag: str, msg: str,
                direction: str = "—") -> None:
    """Publish a synthetic audit log line to the live SSE stream.

    Mirrors smart_gate.main._audit so web request handlers can emit the
    same cmd/ack/warn lines without going through the daemon's bus.
    `direction`: '→' for Pi→ESP, '←' for ESP→Pi, '—' for internal.
    """
    if esp_log_bus is None:
        return
    esp_log_bus.publish({
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "lvl": lvl, "tag": tag, "msg": msg, "direction": direction,
        "synthetic": True,
    })


def create_app(*, db, hub, uart, data_dir: Path, start_time: float | None = None,
               matcher=None, overlay=None, reload_event=None,
               gate_tracker=None, cv2_module=None,
               cap_fps=None, det_fps=None,
               esp_log_bus=None, peripherals=None,
               confirm_timeout_s: float = 3.0) -> Flask:
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
        # Parse query params. _int_param() returns 400 on garbage and
        # clamps to a safe range — guards against `?limit=-1` which
        # SQLite would otherwise treat as "no limit" and dump the table.
        after_id = _int_param("after_id", 0, 0, 2**31 - 1)
        before_id_raw = request.args.get("before_id")
        before_id = _int_param("before_id", 0, 0, 2**31 - 1) if before_id_raw else None
        limit = _int_param("limit", 50, 1, 500)
        methods = request.args.getlist("method") or None
        granted_raw = request.args.get("granted")
        granted = int(granted_raw) if granted_raw in ("0", "1") else None
        q = request.args.get("q") or None

        # Period → ISO timestamp lower bound (server-side resolution).
        # SQLite's events.ts default is datetime('now'), which is UTC.
        # We must compare against UTC, not local time — otherwise the
        # "today" filter is offset by the local TZ (7h in Asia/Ho_Chi_Minh)
        # and silently drops events near the day boundary.
        since = None
        import datetime as _dt
        period = request.args.get("period")
        if period == "today":
            since = _dt.datetime.now(_dt.timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            ).strftime("%Y-%m-%d %H:%M:%S")
        elif period in ("7d", "30d"):
            days = 7 if period == "7d" else 30
            since = (_dt.datetime.now(_dt.timezone.utc)
                     - _dt.timedelta(days=days)
                     ).strftime("%Y-%m-%d %H:%M:%S")

        rows = db.recent_events(limit=limit, after_id=after_id,
                                before_id=before_id, method=methods,
                                granted=granted, q=q, since=since)
        records = [
            {"id": r[0], "ts": r[1], "method": r[2], "user_id": r[3],
             "user_name": r[4], "granted": bool(r[5]),
             "detail": r[6], "clip_path": r[7]}
            for r in rows
        ]
        fmt = request.args.get("format", "json")
        if fmt == "html":
            return render_template("_partials/event_rows.html", rows=records)
        return jsonify(records)

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
        """Manual open/close from web button.

        Two-stage confirmation:
        1. cmd ack from ESP32 → link is alive, ESP32 parsed JSON.
           This is NOT proof the servo moved. Only `link` peripheral
           goes ok here.
        2. Wait up to `confirm_timeout_s` for an evt:gate transition
           that confirms the servo actually moved
           (state=open for verb=open, state=closed for verb=close).
           Only on this confirmation do we return ok=True to the client.

        DB event row is only inserted on confirmation. If the gate
        doesn't transition in time, return 504 with a partial-failure
        body so the dashboard can show 'cmd accepted but not confirmed'.
        """
        _emit_audit(esp_log_bus, "info", "cmd",
                    f"{verb} (manual from web)", direction="→")
        try:
            ack = uart.send_cmd(
                verb,
                {"user": "admin", "reason": "manual"} if verb == "open" else None,
                timeout=2.0,
            )
        except (LinkDown, LinkTimeout) as e:
            err = str(e) or e.__class__.__name__
            _emit_audit(esp_log_bus, "err", "cmd",
                        f"{verb} FAILED: {err} — link unreachable",
                        direction="←")
            if peripherals is not None:
                peripherals.mark_cmd_failed(verb, err)
            return jsonify({"error": err}), 503

        # ack received → link is alive, but servo state still unknown.
        _emit_audit(esp_log_bus, "info", "ack",
                    f"{verb} accepted by ESP32 — đang chờ xác nhận servo…",
                    direction="←")
        if peripherals is not None:
            peripherals.mark_cmd_ack(verb, ok=True, detail=str(ack or ""))

        # Wait for the physical state transition.
        target_state = "open" if verb == "open" else "closed"
        confirmed = False
        if gate_tracker is not None:
            confirmed = gate_tracker.wait_for_state(target_state,
                                                   timeout=confirm_timeout_s)

        if not confirmed:
            _emit_audit(esp_log_bus, "warn", "gate",
                        f"⚠ cmd {verb} ack OK nhưng cổng chưa đạt state={target_state} "
                        f"sau {confirm_timeout_s}s — kiểm tra servo / nguồn",
                        direction="←")
            return jsonify({
                "ok": False,
                "ack": ack,
                "error": f"servo did not reach state={target_state} "
                         f"within {confirm_timeout_s}s",
            }), 504

        # Confirmed by ESP32 — only NOW record the DB event row.
        db.insert_event(method, None, True)
        return jsonify({"ok": True, "ack": ack, "confirmed": True})

    @app.route("/peripherals")
    def peripherals_page():
        return render_template("peripherals.html")

    @app.route("/api/peripherals.json")
    def peripherals_json():
        if peripherals is None:
            return jsonify({"items": [], "warning":
                            "peripheral tracker not configured"})
        return jsonify({"items": peripherals.snapshot()})

    @app.route("/api/users/<name>", methods=["DELETE", "POST"])
    def user_delete(name: str):
        """Delete a user. Cascades face_encodings + qr_tokens via FK.
        Removes the QR PNG. Triggers matcher reload.

        Accepts either DELETE method or POST (forms-friendly, hx-post). For POST,
        only acts if request has `?action=delete` to avoid accidental hits.
        """
        if request.method == "POST" and request.args.get("action") != "delete":
            return jsonify({"error": "use DELETE or POST?action=delete"}), 405
        if not re.match(r"^[A-Za-z0-9_\-]+$", name):
            return jsonify({"error": "invalid name"}), 400
        existed = db.delete_user(name)
        if not existed:
            return jsonify({"error": f"user {name} not found"}), 404
        # Best-effort QR cleanup
        qr_path = qr_dir / f"{name}.png"
        try:
            qr_path.unlink()
        except FileNotFoundError:
            pass
        if reload_event is not None:
            reload_event.set()
        elif matcher is not None:
            matcher.reload(db)
        log.info("deleted user %s (cascade encodings/tokens + qr png)", name)
        return jsonify({"ok": True, "name": name})

    @app.route("/api/users/<name>/rfid", methods=["POST"])
    def api_add_rfid(name: str):
        """Bind an RFID UID to an existing user via cmd:add_uid over UART.

        Body (JSON): {"uid": "<8-20 hex chars>"}

        The firmware allowlist is the source of truth — the daemon does not
        mirror this UID in the SQLite users table; subsequent swipes hit
        the ESP32's NVS allowlist and emit `evt:rfid_swipe` with a name
        the firmware looked up from its own table.

        Returns:
          200 {"ok": true, "uid": ..., "name": ..., "ack": ...} on success
          400 — bad UID hex or missing/invalid name format
          404 — user not in the SQLite users table
          503 — UART unavailable, link down, or timeout
        """
        # 1. Validate user-name format (defensive, route matches free strings)
        if not re.match(r"^[A-Za-z0-9_\-]+$", name):
            return jsonify({"error": "invalid name"}), 400

        # 2. Validate user exists (SQLite side) — keeps the daemon's user
        # table in sync with the firmware allowlist.
        user_id = db.get_user_id_by_name(name)
        if user_id is None:
            return jsonify({"error": f"user not found: {name}"}), 404

        # 3. Validate UID hex
        body = request.get_json(silent=True) or {}
        uid_raw = (body.get("uid") or "").strip()
        if not _UID_RE.match(uid_raw):
            return jsonify({"error": "bad uid (expected 8-20 hex chars)"}), 400
        uid = uid_raw.lower()

        # 4. Send cmd to ESP
        if uart is None:
            return jsonify({"error": "uart not configured"}), 503
        _emit_audit(esp_log_bus, "info", "cmd",
                    f"add_uid uid={uid} name={name}", direction="→")
        try:
            ack = uart.send_cmd("add_uid", {"uid": uid, "name": name},
                                timeout=2.0)
        except (LinkDown, LinkTimeout) as e:
            err = str(e) or e.__class__.__name__
            _emit_audit(esp_log_bus, "err", "cmd",
                        f"add_uid FAILED: {err}", direction="←")
            return jsonify({"error": err}), 503
        except Exception as e:        # noqa: BLE001 — defensive catch-all
            log.exception("cmd:add_uid unexpected error")
            return jsonify({"error": f"uart error: {e}"}), 503

        _emit_audit(esp_log_bus, "info", "ack",
                    f"add_uid OK uid={uid} ack={ack}", direction="←")
        return jsonify({"ok": True, "uid": uid, "name": name, "ack": ack})

    @app.route("/api/users/<name>/rfid/<uid>", methods=["DELETE"])
    def api_remove_rfid(name: str, uid: str):
        """Remove an RFID UID from the firmware allowlist (cmd:remove_uid).

        `name` is included for symmetry with the add endpoint but the firmware
        keys removal by UID only — `name` is not sent. We still 404 if the
        user is unknown so the URL stays well-formed.
        """
        if not re.match(r"^[A-Za-z0-9_\-]+$", name):
            return jsonify({"error": "invalid name"}), 400
        if not _UID_RE.match(uid):
            return jsonify({"error": "bad uid (expected 8-20 hex chars)"}), 400
        if db.get_user_id_by_name(name) is None:
            return jsonify({"error": f"user not found: {name}"}), 404
        if uart is None:
            return jsonify({"error": "uart not configured"}), 503

        uid_lc = uid.lower()
        _emit_audit(esp_log_bus, "info", "cmd",
                    f"remove_uid uid={uid_lc}", direction="→")
        try:
            ack = uart.send_cmd("remove_uid", {"uid": uid_lc}, timeout=2.0)
        except (LinkDown, LinkTimeout) as e:
            err = str(e) or e.__class__.__name__
            _emit_audit(esp_log_bus, "err", "cmd",
                        f"remove_uid FAILED: {err}", direction="←")
            return jsonify({"error": err}), 503
        except Exception as e:        # noqa: BLE001
            log.exception("cmd:remove_uid unexpected error")
            return jsonify({"error": f"uart error: {e}"}), 503

        _emit_audit(esp_log_bus, "info", "ack",
                    f"remove_uid OK uid={uid_lc} ack={ack}", direction="←")
        return jsonify({"ok": True, "uid": uid_lc, "name": name, "ack": ack})

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

    @app.route("/events")
    def events_page():
        return render_template("events.html")

    @app.route("/system")
    def system_page():
        body = _build_healthz_body(db, hub, uart, cap_fps, det_fps,
                                   data_dir, start_time, gate_tracker)
        return render_template("system.html", h=body)

    @app.route("/healthz")
    def healthz():
        body = _build_healthz_body(db, hub, uart, cap_fps, det_fps,
                                   data_dir, start_time, gate_tracker)
        if request.args.get("format") == "html":
            panel = request.args.get("panel", "statusbar")
            if panel == "statusbar":
                return render_template("_partials/statusbar.html", h=body)
            if panel == "banner":
                return render_template("_partials/banner.html", h=body)
            if panel == "quickstats":
                return render_template("_partials/quickstats.html", h=body)
            if panel == "systemcards":
                return render_template("_partials/systemcards.html", h=body)
            return ("unknown panel", 400)
        return jsonify(body)

    @app.route("/api/gate/state.json")
    def gate_state_json():
        """Lightweight endpoint the dashboard polls every 1s for the badge."""
        if gate_tracker is None:
            return jsonify({"state": "unknown", "since_s": 0,
                            "last_user": None})
        return jsonify(gate_tracker.snapshot())

    def _row_to_dict(row):
        # row schema from db.recent_esp_log: (id, ts, lvl, tag, msg)
        return {"id": row[0], "ts": row[1], "lvl": row[2],
                "tag": row[3], "msg": row[4]}

    def _sse_format(item):
        # Synthetic audit messages from main._audit don't carry a DB id —
        # only emit the SSE 'id:' line when a persisted id is present.
        item_id = item.get("id")
        prefix = f"id: {item_id}\n" if item_id else ""
        return (f"{prefix}event: log\n"
                f"data: {json.dumps(item, separators=(',', ':'))}\n\n")

    def _diag(verb: str):
        t0 = time.monotonic()
        try:
            data = uart.send_cmd(verb, timeout=2.0)
        except (LinkDown, LinkTimeout) as e:
            return jsonify({"error": str(e) or e.__class__.__name__}), 503
        ack_ms = int((time.monotonic() - t0) * 1000)
        return jsonify({"ack_ms": ack_ms, "data": data})

    @app.route("/api/diag/ping", methods=["POST"])
    def diag_ping():
        return _diag("ping")

    @app.route("/api/diag/status", methods=["POST"])
    def diag_status():
        return _diag("status")

    @app.route("/api/esp_log")
    def api_esp_log():
        limit = _int_param("limit", 100, 1, 500)
        after_id = _int_param("after_id", 0, 0, 2**31 - 1)
        rows = [_row_to_dict(r) for r in db.recent_esp_log(limit=limit,
                                                           after_id=after_id)]
        fmt = request.args.get("format", "html")
        if fmt == "json":
            return jsonify(rows)
        return render_template("_partials/esp_log_line.html", rows=rows)

    @app.route("/api/esp_log/stream")
    def api_esp_log_stream():
        if esp_log_bus is None:
            return jsonify({"error": "esp_log_bus not configured"}), 503

        last_id = int(request.headers.get("Last-Event-ID", "0") or "0")

        @stream_with_context
        def gen():
            # Subscribe BEFORE replay so any items published during the DB
            # query are still delivered. The live loop will pick them up
            # after the replay finishes.
            q = esp_log_bus.subscribe()
            try:
                if last_id > 0:
                    backlog = db.recent_esp_log(limit=200, after_id=last_id)
                    for row in reversed(backlog):          # oldest first
                        yield _sse_format(_row_to_dict(row))
                last_ping = time.monotonic()
                while True:
                    item = esp_log_bus.wait_for_item(q, timeout=1.0)
                    if item is not None:
                        yield _sse_format(item)
                    now = time.monotonic()
                    if now - last_ping > 15:
                        yield ": ping\n\n"
                        last_ping = now
            except GeneratorExit:
                pass
            finally:
                esp_log_bus.unsubscribe(q)

        return Response(gen(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache",
                                 "X-Accel-Buffering": "no"})

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


def _build_healthz_body(db, hub, uart, cap_fps, det_fps,
                        data_dir, start_time, gate_tracker=None) -> dict:
    import shutil
    expected = {"cap", "detect", "rec", "bus-consumer", "flask",
                "cleanup", "uart-rx", "uart-tx", "uart-hb"}
    active = {t.name for t in threading.enumerate()}
    last_frame_ago = None
    last_ts = getattr(hub, "_last_publish_mono", None)
    if isinstance(last_ts, (int, float)):
        last_frame_ago = max(0.0, time.monotonic() - last_ts)
    n_users = len(db.list_users()) if hasattr(db, "list_users") else None
    try:
        disk_free_gb = shutil.disk_usage(str(data_dir)).free / 1024**3
    except OSError:
        disk_free_gb = None
    body = {
        "uptime_s": int(time.monotonic() - start_time),
        "link_alive": bool(uart.link_alive()),
        "last_frame_ago_s": last_frame_ago,
        "threads_ok": expected.issubset(active),
        "enrolled_users": n_users,
        "cap_fps": round(cap_fps.fps(), 1) if cap_fps else None,
        "det_fps": round(det_fps.fps(), 1) if det_fps else None,
        "events_today": db.count_events_today(),
        "disk_free_gb": round(disk_free_gb, 2) if disk_free_gb is not None else None,
        "last_grant": db.last_grant_event(),
    }
    if gate_tracker is not None:
        body["gate"] = gate_tracker.snapshot()
    return body


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


