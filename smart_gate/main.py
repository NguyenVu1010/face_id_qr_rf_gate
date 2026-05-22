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
from smart_gate.recognition.detector import AuthEvent
from smart_gate.video.framehub import FrameHub
from smart_gate.video.recorder import RingBuffer, RecordingTrigger, run_recorder, cleanup_pass
from smart_gate.video import capture as capture_mod
from smart_gate.link.uart_client import UartClient, EspEvent, LinkDown, LinkTimeout
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
                         args=(cfg, hub, ring, shutdown), daemon=True),
        threading.Thread(target=detector_mod.run_detector, name="detect",
                         args=(cfg, hub, matcher, bus, shutdown), daemon=True),
        threading.Thread(target=run_recorder, name="rec",
                         args=(hub, ring, trig_queue, db, data_dir, cfg, shutdown),
                         daemon=True),
        threading.Thread(target=_consume_bus, name="bus-consumer",
                         args=(bus, db, matcher, uart, trig_queue, cfg, shutdown,
                               reload_event),
                         daemon=True),
        threading.Thread(target=_run_web, name="flask",
                         args=(cfg, db, hub, uart, data_dir, shutdown), daemon=True),
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
                 reload_event: threading.Event) -> None:
    last_grant: dict[int, float] = {}
    last_stranger = 0.0
    while not shutdown.is_set():
        if reload_event.is_set():
            reload_event.clear()
            matcher.reload(db)
            log.info("matcher reloaded")
        try:
            evt = bus.get(timeout=0.5)
        except queue.Empty:
            continue
        if isinstance(evt, AuthEvent):
            _handle_auth_event(evt, db, uart, trig_queue, cfg, last_grant)
            if not evt.granted:
                last_stranger = _maybe_emit_stranger(evt, db, trig_queue,
                                                    cfg, last_stranger)
        elif isinstance(evt, EspEvent):
            _handle_esp_event(evt, db, trig_queue)


def _handle_auth_event(evt: AuthEvent, db, uart, trig_queue, cfg, last_grant):
    now = time.monotonic()
    if evt.granted:
        prev = last_grant.get(evt.user_id, -1e9)
        if now - prev < cfg.recognition.auth_cooldown_s:
            return
        last_grant[evt.user_id] = now
        rows = db.connect().execute("SELECT name FROM users WHERE id=?",
                                    (evt.user_id,)).fetchone()
        name = rows[0] if rows else "?"
        ev_id = db.insert_event(evt.method, evt.user_id, True,
                                detail=str(evt.detail) if evt.detail else None)
        db.touch_last_seen(evt.user_id)
        try:
            uart.send_cmd("open", {"user": name, "reason": evt.method},
                          timeout=2.0)
        except (LinkDown, LinkTimeout) as e:
            log.warning("uart open failed: %s", e)
        try:
            trig_queue.put_nowait(RecordingTrigger(ev_id, evt.ts_mono))
        except queue.Full:
            log.warning("trigger_queue full, dropping clip for event %d", ev_id)


def _maybe_emit_stranger(evt, db, trig_queue, cfg, last_stranger):
    now = time.monotonic()
    if now - last_stranger < cfg.recognition.stranger_cooldown_s:
        return last_stranger
    ev_id = db.insert_event(evt.method, None, False,
                            detail=str(evt.detail) if evt.detail else None)
    try:
        trig_queue.put_nowait(RecordingTrigger(ev_id, evt.ts_mono))
    except queue.Full:
        pass
    return now


def _handle_esp_event(evt: EspEvent, db, trig_queue):
    if evt.v == "log":
        d = evt.data or {}
        db.insert_esp_log(d.get("lvl", "info"), d.get("tag"),
                          d.get("msg", ""))
        return
    if evt.v == "rfid":
        d = evt.data or {}
        result = d.get("result")
        name = d.get("name")
        uid = db.get_user_id_by_name(name) if name else None
        granted = result == "granted"
        ev_id = db.insert_event("rfid", uid, granted,
                                detail=str(d))
        try:
            trig_queue.put_nowait(RecordingTrigger(ev_id, time.monotonic()))
        except queue.Full:
            pass


def _run_web(cfg, db, hub, uart, data_dir, shutdown):
    app = create_app(db=db, hub=hub, uart=uart, data_dir=data_dir)
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
