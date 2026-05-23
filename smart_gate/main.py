"""Daemon orchestrator: start threads, manage lifecycle, signals."""
from __future__ import annotations

import argparse
import logging
import os
import queue
import signal
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from smart_gate.config import load_config
from smart_gate.data.db import Database
from smart_gate.recognition.matcher import Matcher
from smart_gate.recognition import detector as detector_mod
from smart_gate.recognition.detector import AuthEvent, CheckInEvent
from smart_gate.recognition.overlay import OverlayState
from smart_gate.recognition.two_factor import TwoFactorState
from smart_gate.link.gate_state import GateTracker
from smart_gate.video.fps_counter import FpsCounter
from smart_gate.video.framehub import FrameHub
from smart_gate.video.recorder import RingBuffer, RecordingTrigger, run_recorder, cleanup_pass
from smart_gate.video import capture as capture_mod
from smart_gate.link.uart_client import UartClient, EspEvent, LinkDown, LinkTimeout
from smart_gate.link.esp_log_bus import EspLogBus
from smart_gate.web.app import create_app

log = logging.getLogger("smart_gate.main")

# Most-recent shutdown Event, exposed for tests / external triggers.
_current_shutdown: threading.Event | None = None


def main(argv=None) -> int:
    global _current_shutdown
    p = argparse.ArgumentParser(prog="smart_gate")
    p.add_argument("--config", default="/etc/smart-gate/config.toml")
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    _setup_logging(cfg)
    _write_pidfile()

    data_dir = Path(cfg.paths.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "clips").mkdir(exist_ok=True)
    (data_dir / "qr").mkdir(exist_ok=True)

    db = Database(data_dir / "smart_gate.db")
    db.migrate()
    matcher = Matcher(db)

    hub = FrameHub()
    overlay = OverlayState(stale_after_s=2.0)
    two_factor = TwoFactorState(ttl_s=4.0)
    gate_tracker = GateTracker()
    cap_fps = FpsCounter(window_s=5.0)
    det_fps = FpsCounter(window_s=5.0)
    esp_log_bus = EspLogBus()
    ring = RingBuffer(fps=cfg.video.fps, pre_seconds=cfg.recorder.pre_seconds)
    bus: queue.Queue = queue.Queue()
    trig_queue: queue.Queue = queue.Queue(maxsize=5)
    shutdown = threading.Event()
    reload_event = threading.Event()
    _current_shutdown = shutdown

    _install_signal_handlers(shutdown, reload_event)

    uart = UartClient(cfg.link.port, cfg.link.baud, bus, shutdown,
                      ping_interval_s=cfg.link.ping_interval_s,
                      heartbeat_timeout_s=cfg.link.heartbeat_timeout_s)
    uart.start()

    threads = [
        threading.Thread(target=capture_mod.run_capture, name="cap",
                         args=(cfg, hub, ring, shutdown),
                         kwargs={"fps_counter": cap_fps},
                         daemon=True),
        threading.Thread(target=detector_mod.run_detector, name="detect",
                         args=(cfg, hub, matcher, bus, shutdown),
                         kwargs={"overlay": overlay, "state": two_factor,
                                 "fps_counter": det_fps},
                         daemon=True),
        threading.Thread(target=run_recorder, name="rec",
                         args=(hub, ring, trig_queue, db, data_dir, cfg, shutdown),
                         daemon=True),
        threading.Thread(target=_consume_bus, name="bus-consumer",
                         args=(bus, db, matcher, uart, trig_queue, cfg, shutdown,
                               reload_event),
                         kwargs={"state": two_factor,
                                 "gate_tracker": gate_tracker,
                                 "esp_log_bus": esp_log_bus},
                         daemon=True),
        threading.Thread(target=_run_web, name="flask",
                         args=(cfg, db, hub, uart, data_dir, shutdown),
                         kwargs={"matcher": matcher, "overlay": overlay,
                                 "reload_event": reload_event,
                                 "gate_tracker": gate_tracker,
                                 "cap_fps": cap_fps, "det_fps": det_fps,
                                 "esp_log_bus": esp_log_bus},
                         daemon=True),
        threading.Thread(target=_cleanup_loop, name="cleanup",
                         args=(cfg, db, data_dir, shutdown), daemon=True),
        threading.Thread(target=_watchdog, name="watchdog",
                         args=(threading.enumerate, shutdown), daemon=True),
    ]
    for t in threads:
        t.start()

    log.info("smart_gate started (pid %d)", os.getpid())
    shutdown.wait()
    log.info("shutdown requested")
    for t in threads:
        t.join(timeout=15)
    uart.join(timeout=5)
    log.info("smart_gate exited cleanly")
    return 0


def _setup_logging(cfg) -> None:
    Path(cfg.paths.log_dir).mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s"
    )
    level = logging.DEBUG if os.environ.get("SMART_GATE_DEBUG") else \
            getattr(logging, cfg.logging.level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    fh = RotatingFileHandler(
        Path(cfg.paths.log_dir) / "app.log",
        maxBytes=cfg.logging.rotate_mb * 1024 * 1024,
        backupCount=cfg.logging.backup_count,
    )
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.handlers = [fh, sh]


def _install_signal_handlers(shutdown: threading.Event,
                             reload_event: threading.Event) -> None:
    """Install SIGTERM/SIGINT/SIGUSR1 handlers. No-op when called from a
    non-main thread (e.g. inside pytest)."""
    try:
        signal.signal(signal.SIGTERM, lambda *_: shutdown.set())
        signal.signal(signal.SIGINT, lambda *_: shutdown.set())
        signal.signal(signal.SIGUSR1, lambda *_: reload_event.set())
    except ValueError:
        log.warning("signal handlers not installed (not main thread)")


def _write_pidfile() -> None:
    pid_dir = Path("/run/smart-gate")
    try:
        pid_dir.mkdir(parents=True, exist_ok=True)
        (pid_dir / "pid").write_text(str(os.getpid()))
    except PermissionError:
        log.warning("cannot write pidfile (likely running outside systemd)")


def _consume_bus(bus: queue.Queue, db: Database, matcher: Matcher,
                 uart: UartClient, trig_queue: queue.Queue, cfg, shutdown,
                 reload_event: threading.Event,
                 *, state: TwoFactorState | None = None,
                 gate_tracker: GateTracker | None = None,
                 esp_log_bus: EspLogBus | None = None) -> None:
    last_grant: dict[int, float] = {}
    while not shutdown.is_set():
        if reload_event.is_set():
            reload_event.clear()
            matcher.reload(db)
            log.info("matcher reloaded")
        try:
            evt = bus.get(timeout=0.5)
        except queue.Empty:
            continue
        if isinstance(evt, CheckInEvent):
            _handle_checkin(evt, db, matcher, uart, trig_queue, cfg,
                            last_grant, reload_event)
        elif isinstance(evt, AuthEvent):
            # Manual_open / manual_close only — bypasses 2FA.
            _handle_manual_event(evt, db, uart, trig_queue)
        elif isinstance(evt, EspEvent):
            _handle_esp_event(evt, db, matcher, state, trig_queue,
                              uart, cfg, last_grant, reload_event,
                              gate_tracker, esp_log_bus)


def _handle_checkin(evt: CheckInEvent, db, matcher, uart, trig_queue, cfg,
                    last_grant, reload_event):
    """A face + credential pair was observed within TTL. Apply 2FA logic:
    - face matched same user as credential → grant + cmd:open + log event
    - face was unmatched → auto-enroll under credential's user, then grant
    - face matched DIFFERENT user → reject (mismatch event, no cmd:open)
    """
    grant_uid = evt.grant_user_id
    face_uid = evt.face_matched_user_id
    src = evt.grant_source

    # Mismatch: face matched user X, credential said Y, X != Y → security event
    if face_uid is not None and face_uid != grant_uid:
        face_name = matcher.user_name(face_uid) if hasattr(matcher, "user_name") else f"id={face_uid}"
        grant_name = matcher.user_name(grant_uid) if hasattr(matcher, "user_name") else f"id={grant_uid}"
        db.insert_event(
            "mismatch", None, False,
            detail=f"face={face_name} credential={grant_name} src={src}",
        )
        log.warning("checkin mismatch: face=%s credential=%s via %s — gate stays closed",
                    face_name, grant_name, src)
        return

    # Auto-enroll: face unmatched, credential valid. Bind embedding to user.
    if face_uid is None and evt.face_embedding:
        n_samples = db.connect().execute(
            "SELECT COUNT(*) FROM face_encodings WHERE user_id=?", (grant_uid,)
        ).fetchone()[0]
        db.insert_face_encoding(grant_uid, evt.face_embedding, n_samples)
        log.info("auto-enrolled face under user_id=%d via %s (now %d samples)",
                 grant_uid, src, n_samples + 1)
        if reload_event is not None:
            reload_event.set()

    # Cooldown so spam scans don't open the gate repeatedly.
    now = time.monotonic()
    prev = last_grant.get(grant_uid, -1e9)
    if now - prev < cfg.recognition.auth_cooldown_s:
        return
    last_grant[grant_uid] = now

    name = matcher.user_name(grant_uid) if hasattr(matcher, "user_name") else f"id={grant_uid}"
    detail = f"distance={evt.face_distance:.3f}"
    ev_id = db.insert_event(src, grant_uid, True, detail=detail)
    db.touch_last_seen(grant_uid)
    try:
        uart.send_cmd("open", {"user": name, "reason": src}, timeout=2.0)
    except (LinkDown, LinkTimeout) as e:
        log.warning("uart open failed: %s", e)
    try:
        trig_queue.put_nowait(RecordingTrigger(ev_id, evt.ts_mono))
    except queue.Full:
        log.warning("trigger_queue full, dropping clip for event %d", ev_id)


def _handle_manual_event(evt: AuthEvent, db, uart, trig_queue):
    """Manual_open / manual_close from web button — bypasses 2FA."""
    if evt.method not in ("manual_open", "manual_close"):
        return  # ignore legacy face/qr events that shouldn't be emitted now
    verb = "open" if evt.method == "manual_open" else "close"
    payload = {"user": "admin", "reason": "manual"} if verb == "open" else None
    try:
        uart.send_cmd(verb, payload, timeout=2.0)
    except (LinkDown, LinkTimeout) as e:
        log.warning("uart %s failed: %s", verb, e)
    db.insert_event(evt.method, None, True)


def _handle_esp_event(evt: EspEvent, db, matcher, state, trig_queue,
                      uart, cfg, last_grant, reload_event,
                      gate_tracker=None, esp_log_bus=None):
    """ESP32 events. evt:log → esp_log table. evt:rfid → 2FA pairing.
    evt:gate → update GateTracker + log timeout_warn to events table.
    evt:person_passed → just update tracker; gate FSM lives on ESP32."""
    if evt.v == "log":
        d = evt.data or {}
        log_id = db.insert_esp_log(d.get("lvl", "info"), d.get("tag"),
                                   d.get("msg", ""))
        if esp_log_bus is not None:
            esp_log_bus.publish({
                "id":  log_id,
                "ts":  d.get("ts"),
                "lvl": d.get("lvl", "info"),
                "tag": d.get("tag"),
                "msg": d.get("msg", ""),
            })
        return
    if evt.v == "gate" and gate_tracker is not None:
        d = evt.data or {}
        new_state = d.get("state", "")
        prev = gate_tracker.update(new_state)
        # Log only timeout_warn — opening/open/closing/closed are
        # already covered by the cmd/grant event row, no need to spam.
        if new_state == "timeout_warn" and prev != "timeout_warn":
            db.insert_event(
                "timeout", None, False,
                detail=f"no passage detected after gate opened ({prev}→timeout_warn)",
            )
            log.warning("gate timeout_warn — no passage detected; "
                        "ESP32 buzzer should be sounding")
        return
    if evt.v == "person_passed" and gate_tracker is not None:
        # Just informational; FSM on ESP32 will transition to closing next.
        log.info("person passed at %s", evt.data or {})
        return
    if evt.v == "boot" and gate_tracker is not None:
        # Reset our state mirror to idle on ESP32 reboot.
        gate_tracker.update("idle")
        return
    if evt.v == "rfid":
        d = evt.data or {}
        result = d.get("result")
        name = d.get("name")
        uid = db.get_user_id_by_name(name) if name else None
        granted = result == "granted"
        if not granted or uid is None or state is None:
            # Not granted, or unknown UID — no 2FA possible. We deliberately
            # do NOT insert an event row for an isolated RFID-only swipe to
            # avoid the spam the user reported.
            if not granted:
                log.info("rfid denied: %s", d)
            return
        # Pair with current face via two-factor state.
        pair = state.set_grant_and_try_match(uid, "rfid")
        if pair is not None:
            # We're in bus consumer thread already — turn the pair into a
            # CheckInEvent and dispatch it inline.
            checkin = CheckInEvent(
                face_matched_user_id=pair.face_matched_user_id,
                face_embedding=(pair.face_embedding.astype("float32").tobytes()
                                if pair.face_matched_user_id is None else None),
                face_distance=pair.face_distance,
                grant_user_id=pair.grant_user_id,
                grant_source=pair.grant_source,
            )
            _handle_checkin(checkin, db, matcher, uart, trig_queue, cfg,
                            last_grant, reload_event)
        # If pair is None, the grant is held in `state` for up to ttl_s
        # seconds awaiting a face — no event written yet, no gate open.


def _run_web(cfg, db, hub, uart, data_dir, shutdown,
             matcher=None, overlay=None, reload_event=None,
             gate_tracker=None, cap_fps=None, det_fps=None,
             esp_log_bus=None):
    app = create_app(db=db, hub=hub, uart=uart, data_dir=data_dir,
                     matcher=matcher, overlay=overlay,
                     reload_event=reload_event,
                     gate_tracker=gate_tracker,
                     cap_fps=cap_fps, det_fps=det_fps,
                     esp_log_bus=esp_log_bus)
    from werkzeug.serving import make_server
    srv = make_server(cfg.web.host, cfg.web.port, app, threaded=True)
    def watcher():
        shutdown.wait()
        srv.shutdown()
    threading.Thread(target=watcher, daemon=True).start()
    srv.serve_forever()


def _cleanup_loop(cfg, db, data_dir, shutdown):
    if shutdown.wait(30.0):
        return
    while not shutdown.is_set():
        try:
            cleanup_pass(data_dir, db, cfg.recorder.max_age_days,
                         cfg.recorder.max_total_gb)
        except Exception as e:
            log.exception("cleanup pass failed: %s", e)
        if shutdown.wait(3600.0):
            return


def _watchdog(_enum, shutdown):
    while not shutdown.wait(10.0):
        names = {t.name for t in threading.enumerate()}
        expected = {"cap", "detect", "rec", "bus-consumer", "flask",
                    "cleanup", "uart-rx", "uart-tx", "uart-hb"}
        missing = expected - names
        if missing:
            log.warning("threads missing: %s", missing)
