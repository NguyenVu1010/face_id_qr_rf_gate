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
from smart_gate.data.esp_log_writer import EspLogWriter
from smart_gate.recognition.matcher import Matcher
from smart_gate.recognition import detector as detector_mod
from smart_gate.recognition.detector import AuthEvent, CheckInEvent
from smart_gate.recognition.overlay import OverlayState
from smart_gate.recognition.auto_enroll_pair import (
    AutoEnrollPairState,
    EnrollCandidate,
)
from smart_gate.recognition.cooldown import UserCooldown
from smart_gate.link.gate_state import GateTracker
from smart_gate.link.peripheral_status import PeripheralTracker
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


def _cap_rfid_fields(d: dict) -> tuple[str, str]:
    """Truncate ESP-supplied name/uid to firmware-buffer-sized limits.

    Firmware uses e.name[32] and e.uid[24]; a misbehaving ESP could in
    principle send much longer strings. Bound them at the protocol
    boundary so log lines, SQL binds, and dashboard renders are all safe.
    """
    name = (d.get("name") or "")[:32]
    uid  = (d.get("uid")  or "")[:24]
    return name, uid


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
    # 1-of-3 channel cooldowns + RFID-only auto-enroll pairing.
    # Each auth channel now fires its own CheckInEvent independently; the
    # per-user cooldown suppresses duplicate fires while the same user
    # stays in frame / keeps the card on the reader.
    face_cooldown = UserCooldown(cfg.recognition.face_cooldown_s)
    qr_cooldown = UserCooldown(cfg.recognition.qr_cooldown_s)
    auto_enroll_state = AutoEnrollPairState(
        ttl_s=cfg.recognition.autoenroll_ttl_s)
    gate_tracker = GateTracker()
    peripherals = PeripheralTracker()
    cap_fps = FpsCounter(window_s=5.0)
    det_fps = FpsCounter(window_s=5.0)
    esp_log_bus = EspLogBus()
    esp_log_writer = EspLogWriter(db)
    esp_log_writer.start()
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
                         kwargs={"overlay": overlay,
                                 "face_cooldown": face_cooldown,
                                 "qr_cooldown": qr_cooldown,
                                 "auto_enroll_state": auto_enroll_state,
                                 "fps_counter": det_fps},
                         daemon=True),
        threading.Thread(target=run_recorder, name="rec",
                         args=(hub, ring, trig_queue, db, data_dir, cfg, shutdown),
                         daemon=True),
        threading.Thread(target=_consume_bus, name="bus-consumer",
                         args=(bus, db, matcher, uart, trig_queue, cfg, shutdown,
                               reload_event),
                         kwargs={"auto_enroll_state": auto_enroll_state,
                                 "gate_tracker": gate_tracker,
                                 "esp_log_bus": esp_log_bus,
                                 "esp_log_writer": esp_log_writer,
                                 "peripherals": peripherals},
                         daemon=True),
        threading.Thread(target=_run_web, name="flask",
                         args=(cfg, db, hub, uart, data_dir, shutdown),
                         kwargs={"matcher": matcher, "overlay": overlay,
                                 "reload_event": reload_event,
                                 "gate_tracker": gate_tracker,
                                 "cap_fps": cap_fps, "det_fps": det_fps,
                                 "esp_log_bus": esp_log_bus,
                                 "peripherals": peripherals},
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
    # Flush any tail of pending ESP log rows before exit.
    esp_log_writer.stop(timeout=2.0)
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
                 *, auto_enroll_state: AutoEnrollPairState | None = None,
                 gate_tracker: GateTracker | None = None,
                 esp_log_bus: EspLogBus | None = None,
                 esp_log_writer: EspLogWriter | None = None,
                 peripherals: PeripheralTracker | None = None) -> None:
    # Per-channel cooldowns live in the detector now (face_cooldown /
    # qr_cooldown). last_grant is retained as an opaque handle for the
    # checkin signature — _handle_checkin no longer reads it.
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
        try:
            if isinstance(evt, CheckInEvent):
                _handle_checkin(evt, db, matcher, uart, trig_queue, cfg,
                                last_grant, reload_event, esp_log_bus,
                                gate_tracker=gate_tracker)
            elif isinstance(evt, AuthEvent):
                # Manual_open / manual_close only — bypasses 1-of-3 routing.
                _handle_manual_event(evt, db, uart, trig_queue, esp_log_bus)
            elif isinstance(evt, EspEvent):
                _handle_esp_event(evt, db, matcher, bus, trig_queue,
                                  uart, cfg, last_grant, reload_event,
                                  auto_enroll_state=auto_enroll_state,
                                  gate_tracker=gate_tracker,
                                  esp_log_bus=esp_log_bus,
                                  esp_log_writer=esp_log_writer,
                                  peripherals=peripherals)
        except Exception:
            # An unhandled exception in a handler (DB write failure, schema
            # drift, etc.) used to kill this thread silently — daemon stayed
            # "running" but processed no events. Log it, emit a synthetic
            # audit so the operator sees it on the dashboard, back off, and
            # keep going.
            log.exception("bus consumer iter failed; continuing")
            try:
                _audit(esp_log_bus, "error", "internal",
                       "bus consumer exception — see app.log")
            except Exception:
                pass
            time.sleep(0.5)


def _audit(esp_log_bus, lvl: str, tag: str, msg: str,
           direction: str = "—") -> None:
    """Publish a synthetic log line to the live audit stream.
    `direction` is "→" for Pi→ESP, "←" for ESP→Pi, "—" for internal."""
    if esp_log_bus is None:
        return
    esp_log_bus.publish({
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "lvl": lvl, "tag": tag, "msg": msg, "direction": direction,
        "synthetic": True,
    })


def _handle_checkin(evt: CheckInEvent, db, matcher, uart, trig_queue, cfg,
                    last_grant, reload_event, esp_log_bus=None,
                    gate_tracker: GateTracker | None = None):
    """1-of-3 channel router. Each method writes exactly one event row.

    - face / qr → Pi sends cmd:open to ESP (ESP doesn't know about these).
    - rfid     → ESP already opened the gate via its NVS allowlist shortcut.
                 Pi only mirrors the event row; sending cmd:open again would
                 race with the ESP's in-flight ack and double-log.

    Per-channel cooldowns live upstream (detector's `face_cooldown` /
    `qr_cooldown`; ESP allowlist for RFID). `last_grant` is unused here
    today — kept in the signature for future cross-channel throttling.
    """
    del last_grant  # explicitly unused — see docstring
    name = matcher.user_name(evt.user_id)
    if name is None or name == f"id={evt.user_id}":
        # Matcher returns "id=<n>" when the user_id isn't in its name map.
        # That happens for unknown users — refuse to write an event row.
        _audit(esp_log_bus, "warn", evt.method,
               f"unknown user_id={evt.user_id}")
        return

    # Attribute the latest open to a name for the dashboard widget. Must
    # happen before any potential exception path below so the field reflects
    # the user even if downstream DB / UART work raises.
    if gate_tracker is not None:
        gate_tracker.set_last_user(name)

    # Channel-specific detail field for the event row.
    if evt.face_distance is not None:
        detail = f"distance={evt.face_distance:.3f}"
    elif evt.raw_uid is not None:
        detail = f"uid={evt.raw_uid}"
    elif evt.qr_token is not None:
        detail = f"token={evt.qr_token}"
    else:
        detail = None

    # Wrap the event-row insert + last_seen update in one transaction so
    # both writes share a single fsync instead of two (NORMAL sync still
    # flushes WAL on each COMMIT).
    with db.transaction():
        ev_id = db.insert_event(evt.method, evt.user_id, True, detail=detail)
        db.touch_last_seen(evt.user_id)

    # RFID already opened the gate on the ESP side — don't duplicate.
    if evt.method != "rfid":
        _audit(esp_log_bus, "info", "cmd",
               f"open user={name} reason={evt.method}", direction="→")
        try:
            ack = uart.send_cmd("open", {"user": name, "reason": evt.method},
                                timeout=2.0)
            _audit(esp_log_bus, "info", "ack",
                   f"open OK ({ack})" if ack else "open ack",
                   direction="←")
        except (LinkDown, LinkTimeout) as e:
            log.warning("uart open failed: %s", e)
            _audit(esp_log_bus, "err", "cmd",
                   f"open FAILED: {e} — peripheral unreachable",
                   direction="←")
    else:
        _audit(esp_log_bus, "info", "rfid",
               f"granted user={name} (ESP already opened)", direction="←")

    try:
        trig_queue.put_nowait(RecordingTrigger(ev_id, evt.ts_mono))
    except queue.Full:
        log.warning("trigger_queue full, dropping clip for event %d", ev_id)


def _trigger_auto_enroll(enroll: EnrollCandidate, db, matcher,
                         reload_event, esp_log_bus=None) -> None:
    """RFID-paired auto-enroll: insert a new face_encoding row for the
    grant user and signal the matcher to reload."""
    user_name = matcher.user_name(enroll.grant_user_id)
    if user_name is None or user_name == f"id={enroll.grant_user_id}":
        return
    # sample_idx = current count so each insert gets a unique index.
    n_samples = db.connect().execute(
        "SELECT COUNT(*) FROM face_encodings WHERE user_id=?",
        (enroll.grant_user_id,),
    ).fetchone()[0]
    db.insert_face_encoding(enroll.grant_user_id,
                            enroll.embedding.astype("float32").tobytes(),
                            n_samples)
    log.info("auto-enrolled face under user_id=%d via rfid (now %d samples)",
             enroll.grant_user_id, n_samples + 1)
    _audit(esp_log_bus, "info", "enroll",
           f"auto-bind face → {user_name} via rfid (sample {n_samples + 1})",
           direction="—")
    if reload_event is not None:
        reload_event.set()


def _handle_manual_event(evt: AuthEvent, db, uart, trig_queue, esp_log_bus=None):
    """Manual_open / manual_close from web button — bypasses 2FA."""
    if evt.method not in ("manual_open", "manual_close"):
        return  # ignore legacy face/qr events that shouldn't be emitted now
    verb = "open" if evt.method == "manual_open" else "close"
    payload = {"user": "admin", "reason": "manual"} if verb == "open" else None
    _audit(esp_log_bus, "info", "cmd",
           f"{verb} (manual from web)", direction="→")
    try:
        ack = uart.send_cmd(verb, payload, timeout=2.0)
        _audit(esp_log_bus, "info", "ack",
               f"{verb} OK ({ack})" if ack else f"{verb} ack",
               direction="←")
    except (LinkDown, LinkTimeout) as e:
        log.warning("uart %s failed: %s", verb, e)
        _audit(esp_log_bus, "err", "cmd",
               f"{verb} FAILED: {e} — peripheral unreachable",
               direction="←")
    db.insert_event(evt.method, None, True)


def _handle_esp_event(evt: EspEvent, db, matcher, bus, trig_queue,
                      uart, cfg, last_grant, reload_event, *,
                      auto_enroll_state: AutoEnrollPairState | None = None,
                      gate_tracker=None, esp_log_bus=None,
                      esp_log_writer: EspLogWriter | None = None,
                      peripherals=None):
    """ESP32 events. evt:log → esp_log table + PeripheralTracker.
    evt:rfid → enqueue CheckInEvent(method='rfid') + optional auto-enroll.
    evt:gate → update GateTracker + log timeout_warn.
    evt:heartbeat → mark link alive."""
    if evt.v == "log":
        d = evt.data or {}
        lvl = d.get("lvl", "info")
        tag = d.get("tag")
        msg = d.get("msg", "")
        # Hot path (up to 20 Hz): enqueue to batched writer instead of one
        # synchronous INSERT+fsync per line. Fall back to the sync writer
        # if no writer was wired (CLI tooling, tests, …).
        if esp_log_writer is not None:
            esp_log_writer.enqueue((lvl, tag, msg))
        else:
            db.insert_esp_log(lvl, tag, msg)
        if esp_log_bus is not None:
            # The DB id is no longer known synchronously (batched). The SSE
            # formatter handles the absent-id case by omitting the SSE
            # 'id:' line — same path used for synthetic audit events.
            esp_log_bus.publish({
                "ts":  d.get("ts"),
                "lvl": lvl,
                "tag": tag,
                "msg": msg,
            })
        if peripherals is not None:
            peripherals.update_from_log(
                lvl=d.get("lvl", "info"), tag=d.get("tag"),
                msg=d.get("msg", ""), ts=d.get("ts"),
            )
        return
    if evt.v == "heartbeat" and peripherals is not None:
        peripherals.mark_heartbeat()
        # fallthrough: nothing else to do for heartbeat
    if evt.v == "gate":
        d = evt.data or {}
        new_state = d.get("state", "")
        # Brown-out / panic / watchdog recovery (firmware Task 3.10):
        # ESP boots, finds last_state was mid-cycle (OPENING/OPEN/CLOSING/
        # TIMEOUT_WARN) and holds servo at 90° neutral for 5 s instead of
        # snapping closed. Surface this loudly: dashboard banner + permanent
        # row in /events history so the operator can audit afterwards.
        # Handle even when gate_tracker is None (CLI tooling, tests).
        if new_state == "unknown":
            reason = d.get("reset_reason", "?")
            _audit(esp_log_bus, "error", "boot",
                   f"ESP recovered from {reason} — gate state unknown, "
                   f"verify passage clear",
                   direction="←")
            try:
                db.insert_event("system", None, False,
                                detail=f"esp_recovery_{reason}")
            except Exception:
                log.exception("failed to insert recovery event")
            # Do NOT feed gate_tracker.update("unknown") — _KNOWN_STATES
            # fallback would silently coerce to "idle", masking the
            # mid-cycle reboot from anyone watching tracker state.
            return
        if gate_tracker is None:
            return
        prev = gate_tracker.update(new_state)
        # Feed PeripheralTracker: opening/open/closing/closed = servo moved.
        if peripherals is not None:
            peripherals.mark_gate_state(new_state)
        # Log only timeout_warn — opening/open/closing/closed are
        # already covered by the cmd/grant event row, no need to spam.
        if new_state == "timeout_warn" and prev != "timeout_warn":
            db.insert_event(
                "timeout", None, False,
                detail=f"no passage detected after gate opened ({prev}→timeout_warn)",
            )
            log.warning("gate timeout_warn — no passage detected; "
                        "ESP32 buzzer should be sounding")
            _audit(esp_log_bus, "warn", "gate",
                   "timeout — không có người đi qua, buzzer kêu",
                   direction="←")
        elif new_state == "open" and prev not in ("open", "opening"):
            _audit(esp_log_bus, "info", "gate",
                   "✓ cổng đã mở (servo confirmed)",
                   direction="←")
        elif new_state == "opening":
            _audit(esp_log_bus, "info", "gate",
                   "đang mở…", direction="←")
        elif new_state == "closing":
            _audit(esp_log_bus, "info", "gate",
                   "đang đóng…", direction="←")
        elif new_state == "closed":
            _audit(esp_log_bus, "info", "gate",
                   "✓ cổng đã đóng", direction="←")
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
        # Defensive bound: cap ESP-supplied strings at firmware buffer sizes
        # (e.name[32], e.uid[24]) BEFORE they reach log lines / SQL binds /
        # dashboard renders. A misbehaving ESP must not be able to OOM the Pi.
        name, raw_uid = _cap_rfid_fields(d)
        uid = db.get_user_id_by_name(name) if name else None
        granted = result == "granted"
        if peripherals is not None:
            peripherals.mark_rfid_scan(granted, name)
        if not granted:
            # Denied — do NOT write an event row (avoids spam from random
            # cards near the reader). Audit only.
            _audit(esp_log_bus, "warn", "rfid",
                   f"denied uid={raw_uid[:8]}… name={name or '(unknown)'}",
                   direction="←")
            log.info("rfid denied: %s", d)
            return
        if uid is None:
            # Granted by the ESP allowlist but unknown to the Pi DB — log
            # and skip the mirror row + auto-enroll. (Shouldn't happen in
            # normal operation; allowlist sync is server→ESP.)
            _audit(esp_log_bus, "warn", "rfid",
                   f"granted on ESP but unknown to Pi: name={name}",
                   direction="←")
            return
        # ESP already opened the gate. Mirror it as a CheckInEvent on the
        # bus so all DB writes and trigger handling go through one path.
        bus.put(CheckInEvent(method="rfid", user_id=uid, raw_uid=raw_uid))
        # Optionally seed RFID-triggered face auto-enroll.
        if (auto_enroll_state is not None
                and getattr(cfg.recognition, "autoenroll_enabled", True)):
            enroll = auto_enroll_state.set_grant_and_wait_for_face(uid, "rfid")
            if enroll is not None:
                _trigger_auto_enroll(enroll, db, matcher,
                                     reload_event, esp_log_bus)
        return


def _run_web(cfg, db, hub, uart, data_dir, shutdown,
             matcher=None, overlay=None, reload_event=None,
             gate_tracker=None, cap_fps=None, det_fps=None,
             esp_log_bus=None, peripherals=None):
    app = create_app(db=db, hub=hub, uart=uart, data_dir=data_dir,
                     matcher=matcher, overlay=overlay,
                     reload_event=reload_event,
                     gate_tracker=gate_tracker,
                     cap_fps=cap_fps, det_fps=det_fps,
                     esp_log_bus=esp_log_bus,
                     peripherals=peripherals)
    from werkzeug.serving import make_server
    try:
        srv = make_server(cfg.web.host, cfg.web.port, app, threaded=True)
    except (OSError, SystemExit) as e:
        # werkzeug catches EADDRINUSE internally and calls sys.exit(1),
        # so we must catch SystemExit as well as bare OSError.
        log.critical("web bind failed on %s:%d: %s - shutting down",
                     cfg.web.host, cfg.web.port, e)
        shutdown.set()
        return
    def watcher():
        shutdown.wait()
        srv.shutdown()
    threading.Thread(target=watcher, daemon=True).start()
    try:
        srv.serve_forever()
    except OSError as e:
        log.critical("web serve failed: %s - shutting down", e)
        shutdown.set()


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
