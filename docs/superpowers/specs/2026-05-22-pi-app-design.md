# Smart Gate — Pi 5 Application Design Spec

**Date:** 2026-05-22
**Status:** Design draft awaiting review
**Scope:** Software design for the Raspberry Pi 5 side of `smart_gate`. Consumes [2026-05-21-smart-gate-architecture-design.md](2026-05-21-smart-gate-architecture-design.md) §3 (video pipeline) and §4 (UART protocol) as immutable contracts. Defines the Python application: module layout, threading model, SQLite schema, recognition pipeline, UART client, recorder, Flask admin, CLI, configuration, logging, systemd unit, and test strategy. Hardware design, ESP32 firmware, and KiCad/FreeCAD files are out of scope.

**Definition of done:** stable demo runnable continuously 1–2 weeks on a single Pi 5 with systemd auto-restart and persistent logs. Unit tests cover protocol/matcher/recorder/db; integration tests use mocked serial and camera. No CI; no Docker; no cloud.

---

## 1. Overview

A single Python 3.11 process (`python -m smart_gate`) running 8 threads, fan-out via `FrameHub`. systemd manages the daemon's lifecycle. A separate CLI process (`python -m smart_gate.cli`) handles enrollment, QR rotation, user management, and event tailing — it touches only the SQLite file and the QR PNG directory, never the daemon's memory. Communication between daemon and CLI for cache invalidation is via `SIGUSR1`.

```
                    systemd: smart-gate.service
                                │
                                ▼ python -m smart_gate
   ┌─────────────────── 1 PROCESS, 8 THREADS ────────────────────┐
   │                                                              │
   │  video/      capture  framehub  recorder                     │
   │  recognition/ detector  matcher                              │
   │  link/       uart_client (rx, tx, heartbeat)  protocol       │
   │  web/        flask  templates/  static/                      │
   │  data/       db (SQLite WAL)  models  migrations/            │
   │  main.py     orchestrator: signals, lifecycle, watchdog      │
   │                                                              │
   └────────────┬─────────────────────────────────────────────────┘
                │ /dev/ttyUSB0 (115200, JSON Lines)
                ▼
                ESP32 (architecture spec §4)

   Side-channel: python -m smart_gate.cli enroll | qr | users | events
```

---

## 2. Module layout

```
smart_gate/
├── __init__.py
├── __main__.py             # entry: python -m smart_gate
├── main.py                 # orchestrator (start threads, signals, shutdown)
├── config.py               # tomllib loader + defaults
├── video/
│   ├── __init__.py
│   ├── capture.py          # cv2 V4L2 thread
│   ├── framehub.py         # threading.Condition fan-out
│   └── recorder.py         # ring buffer + ffmpeg + cleanup
├── recognition/
│   ├── __init__.py
│   ├── detector.py         # MediaPipe + face_recognition + pyzbar thread
│   └── matcher.py          # in-memory index, reload on SIGUSR1
├── link/
│   ├── __init__.py
│   ├── uart_client.py      # rx/tx/heartbeat threads
│   └── protocol.py         # JSON Lines codec (pure functions)
├── web/
│   ├── __init__.py
│   ├── app.py              # Flask app factory + routes
│   ├── templates/
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   └── users.html
│   └── static/
│       ├── htmx.min.js
│       └── pico.min.css
├── data/
│   ├── __init__.py
│   ├── db.py               # connection pool, threading.local
│   ├── models.py           # dataclasses User, Event, FaceEncoding, QrToken
│   └── migrations/
│       └── 0001_init.sql
└── cli/
    ├── __init__.py
    ├── __main__.py         # argparse dispatcher
    ├── enroll.py
    ├── qr.py
    ├── users.py
    └── events.py
tests/
├── unit/
│   ├── test_protocol.py
│   ├── test_matcher.py
│   ├── test_recorder.py
│   ├── test_db.py
│   └── test_config.py
├── integration/
│   ├── mocks/
│   │   ├── serial.py
│   │   └── camera.py
│   └── test_pipeline.py
└── conftest.py
packaging/
├── smart-gate.service
└── config.default.toml
scripts/
└── install.sh
requirements.txt
README.md
```

---

## 3. Threading & lifecycle

### 3.1 Threads

| # | Name | Module | Purpose |
|---|---|---|---|
| 1 | `cap` | `video/capture.py` | cv2.VideoCapture loop, encode JPEG, publish to FrameHub + push to recorder ring buffer |
| 2 | `detect` | `recognition/detector.py` | Pull BGR, run MediaPipe + face_recognition + pyzbar, emit AuthEvent |
| 3 | `rec` | `video/recorder.py` | Ring-buffer JPEGs, on event run ffmpeg, write clip |
| 4 | `rx` | `link/uart_client.py` | Read `/dev/ttyUSB0` lines, parse JSON, dispatch |
| 5 | `tx` | `link/uart_client.py` | Serialize tx_queue items to port (single writer) |
| 6 | `heartbeat` | `link/uart_client.py` | Send `cmd:ping` every 5 s |
| 7 | `flask` | `web/app.py` | Werkzeug threaded server bound 0.0.0.0:8080 |
| 8 | `watchdog` | `main.py` | Tick-monitor for threads 1–7; log WARN if stale > 30 s |

### 3.2 Startup order (`main.py`)

1. Parse `--config /path/to/config.toml` (default `/etc/smart-gate/config.toml`).
2. Open SQLite `data/smart_gate.db`, run pending migrations.
3. Construct `FrameHub`, `EventBus` (`queue.Queue`, unbounded), `UartClient`, `Matcher` (loads from DB).
4. Register signal handlers: SIGTERM, SIGINT → `shutdown_event.set()`; SIGUSR1 → `reload_event.set()`.
5. Start threads in order: `rx`, `heartbeat`, `cap`, `detect`, `rec`, `flask`, `watchdog`.
6. `main` blocks on `shutdown_event.wait()`.

### 3.3 Shutdown

1. SIGTERM received → `shutdown_event.set()`.
2. `cap` closes cv2 device, `FrameHub.publish(None, None)` to wake consumers, exits.
3. `detect`, `rec` see None frame or shutdown_event, drain in-flight work, exit.
4. `rec` waits for running `ffmpeg` subprocess up to 10 s, then `kill()`.
5. `rx` closes serial port; `tx` drains tx_queue (best-effort), exits; `heartbeat` exits.
6. `flask` shutdown via werkzeug `srv.shutdown()`.
7. `main` `join()` all with 15 s timeout. Any thread still alive → `os._exit(1)` so systemd restarts cleanly.

### 3.4 Error recovery

| Failure | Handler |
|---|---|
| Webcam read fails 30× consecutive (~2 s) | `cap` reopens device. If reopen fails, retry every 5 s. FrameHub flags "stale"; `/stream.mjpeg` returns placeholder JPEG. |
| `serial.SerialException` in `rx` or `tx` | Close port, retry open with exponential backoff 1→2→5→10→30 s. `heartbeat` pauses sending. `/api/gate/open` returns 503. |
| ffmpeg crash or timeout (30 s) | Recorder logs WARN, deletes tempdir, `UPDATE events SET clip_path=NULL`. |
| SQLite `OperationalError: database is locked` | `busy_timeout = 5000` ms set on connect; effectively never triggers at our write rate. |
| Disk free < 200 MB | Skip clip ffmpeg for the event (still INSERT event row with NULL clip_path). Cleanup thread runs early to free space. |
| Thread silently stuck (last tick > 30 s) | `watchdog` logs WARN. Operator-visible signal; no automatic kill. |

### 3.5 Concurrency rules

- **SQLite:** one connection per thread via `threading.local()`. WAL mode + `busy_timeout=5000`. Writers: `detect`, `rx`, `rec`, `flask`. Readers: `flask`, `watchdog`, CLI.
- **FrameHub:** `cap` is sole publisher; consumers wait on `Condition`. Publishing with no waiter is a no-op.
- **EventBus:** `queue.Queue`, unbounded (events/min, not /sec). Producers: `detect`, `rx`. Consumers: `rec`, `tx` (via debouncer), `db_writer` (inlined in producer thread for simplicity).
- **UART tx:** all `cmd:*` writes funnel through a single `tx` thread reading from `tx_queue`. No concurrent `port.write()`.

---

## 4. SQLite schema (`data/migrations/0001_init.sql`)

```sql
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;

CREATE TABLE users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    last_seen   TEXT,
    note        TEXT
);

CREATE TABLE face_encodings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    embedding   BLOB    NOT NULL,   -- 128 × float32 = 512 bytes
    sample_idx  INTEGER NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_face_user ON face_encodings(user_id);

CREATE TABLE qr_tokens (
    token       TEXT    PRIMARY KEY,         -- 32 hex chars (16 bytes random)
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    revoked_at  TEXT
);
CREATE UNIQUE INDEX idx_qr_active_user
    ON qr_tokens(user_id) WHERE revoked_at IS NULL;

CREATE TABLE events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL DEFAULT (datetime('now')),
    method      TEXT    NOT NULL,            -- 'face' | 'qr' | 'rfid' | 'manual_open' | 'manual_close'
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    granted     INTEGER NOT NULL,            -- 0 | 1
    detail      TEXT,                         -- JSON
    clip_path   TEXT
);
CREATE INDEX idx_events_ts ON events(ts DESC);

CREATE TABLE esp_log (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    ts   TEXT NOT NULL DEFAULT (datetime('now')),
    lvl  TEXT NOT NULL,
    tag  TEXT,
    msg  TEXT NOT NULL
);
```

Highlights:
- **3–5 face samples per user**, stored individually. Match returns `min(distance(probe, sample))` per user, then user with overall min distance. Linear scan over ≤ 200 vectors is ~1 ms.
- **Embedding as float32 BLOB** (512 B/sample). `numpy.frombuffer(blob, dtype='float32')` to load.
- **One active QR per user** enforced by partial unique index; rotate = revoke old + insert new in a single transaction.
- **Stranger events** (face detected but no match within threshold) recorded with `user_id=NULL, granted=0`. Debouncer suppresses repeats.
- **RFID events mirrored** from ESP32 `evt:rfid` so the single `events` table is the canonical entry log.
- **`esp_log` separate** from `events` so log spam doesn't dilute the entry history; rotated by row count (keep last 10 000).

### 4.1 Matching thresholds

- `face_threshold = 0.55` (face_recognition Euclidean). Default `0.6` is too lax for a demo of low base rate.
- `uncertain_band = [0.55, 0.65]` — matches in this band are silently dropped (neither grant nor stranger event), waiting for a clearer frame.
- `distance > 0.65` with face_detected=True → stranger event.

---

## 5. Recognition pipeline (`recognition/`)

### 5.1 Per-frame work in `detector.py`

```python
def process_frame(bgr, mp_detector, matcher, bus, cfg):
    # 1. QR decode
    for sym in pyzbar.decode(bgr):
        token = sym.data.decode('utf-8', errors='replace')
        user_id = matcher.lookup_qr(token)
        if user_id is not None:
            bus.put(AuthEvent('qr', user_id, granted=True))
        # No "stranger" QR event: bad tokens are silent.

    # 2. Face detect
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    result = mp_detector.process(rgb)
    if not result.detections:
        return
    box = best_box(result.detections, rgb.shape)  # highest score
    roi = pad_and_crop(rgb, box, pad=0.20)
    encodings = face_recognition.face_encodings(roi, num_jitters=1)
    if not encodings:
        return
    probe = encodings[0].astype('float32')
    user_id, distance = matcher.match_face(probe)
    if user_id is not None and distance < cfg.face_threshold:
        bus.put(AuthEvent('face', user_id, granted=True, detail={'distance': float(distance)}))
    elif distance > cfg.uncertain_band[1]:
        bus.put(AuthEvent('face', None, granted=False, detail={'distance': float(distance)}))
    # else: uncertain band → drop
```

Detector achievable throughput on Pi 5: ~10 fps (1 face/frame, 60–80 ms per frame). FrameHub captures 15 fps; detector drops 30–50% — fine, always processes the latest.

### 5.2 Matcher

```python
class Matcher:
    def __init__(self, db):
        self._lock = threading.RLock()
        self._faces = []       # list[(user_id, np.ndarray[128, float32])]
        self._qrs = {}         # token -> user_id
        self.reload(db)

    def reload(self, db):
        with self._lock:
            self._faces = db.load_all_face_encodings()
            self._qrs = db.load_active_qr_tokens()

    def match_face(self, probe):
        with self._lock:
            best_user = None
            best_dist = float('inf')
            user_dists = {}
            for user_id, enc in self._faces:
                d = np.linalg.norm(probe - enc)
                if d < user_dists.get(user_id, float('inf')):
                    user_dists[user_id] = d
            for user_id, d in user_dists.items():
                if d < best_dist:
                    best_dist = d
                    best_user = user_id
            return best_user, best_dist

    def lookup_qr(self, token):
        with self._lock:
            return self._qrs.get(token)
```

`reload()` called: at startup, on SIGUSR1 (after CLI mutation).

### 5.3 Auth debouncer

Inline in the EventBus consumer side (in `main.py` orchestrator or wrapped consumer):

- `last_grant: dict[int, float]` — user_id → monotonic timestamp of last granted event.
- `last_stranger: float` — monotonic timestamp of last stranger event.

```python
def should_emit(event):
    now = time.monotonic()
    if event.granted:
        if now - last_grant.get(event.user_id, -1e9) < cfg.auth_cooldown_s:
            return False
        last_grant[event.user_id] = now
        return True
    else:  # stranger
        if now - last_stranger < cfg.stranger_cooldown_s:
            return False
        last_stranger = now
        return True
```

`auth_cooldown_s = 5`, `stranger_cooldown_s = 30`. Configurable.

### 5.4 AuthEvent dataclass

```python
@dataclass
class AuthEvent:
    method: str                # 'face' | 'qr'
    user_id: int | None
    granted: bool
    detail: dict = field(default_factory=dict)
    ts_mono: float = field(default_factory=time.monotonic)
```

After debouncer accepts, the event is dispatched to:
1. `data.db.insert_event(...)` → `events` row, returns `event_id`.
2. `link.uart.send_cmd("open", {"user": name, "reason": method})` if granted.
3. `recorder.record_queue.put(RecordingTrigger(event_id, ts_mono))`.

---

## 6. UART client (`link/`)

### 6.1 Protocol module (pure functions)

```python
# link/protocol.py
MAX_LINE = 512
VERBS_CMD = frozenset({"open","close","add_uid","remove_uid","list_uids","config","status","ping"})
VERBS_EVT = frozenset({"boot","rfid","gate","person_passed","heartbeat","log"})

class ProtocolError(ValueError): pass

def encode(typ: str, v: str, data: dict | None = None, msg_id: int | None = None) -> bytes:
    obj = {}
    if msg_id is not None: obj["id"] = msg_id
    obj["type"] = typ
    obj["v"] = v
    if data is not None: obj["data"] = data
    line = (json.dumps(obj, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    if len(line) > MAX_LINE:
        raise ProtocolError(f"line too long: {len(line)} > {MAX_LINE}")
    return line

def decode(line: bytes) -> dict:
    line = line.rstrip(b"\r\n")
    if not line:
        raise ProtocolError("empty line")
    if len(line) > MAX_LINE:
        raise ProtocolError(f"line too long: {len(line)}")
    try:
        obj = json.loads(line)
    except json.JSONDecodeError as e:
        raise ProtocolError(f"bad json: {e}") from e
    if not isinstance(obj, dict) or "type" not in obj or "v" not in obj:
        raise ProtocolError("missing required field")
    if obj["type"] not in {"cmd","evt","ack"}:
        raise ProtocolError(f"bad type: {obj['type']}")
    return obj
```

### 6.2 `UartClient`

```python
class UartClient:
    def __init__(self, port_path, baud, event_bus, shutdown):
        self._port_path = port_path
        self._baud = baud
        self._ser = None
        self._port_lock = threading.Lock()
        self._tx_queue = queue.Queue()
        self._next_id = itertools.count(1)
        self._pending = {}                 # msg_id -> threading.Event + result holder
        self._pending_lock = threading.Lock()
        self._last_rx = 0.0
        self._bus = event_bus
        self._shutdown = shutdown
        self._connected = threading.Event()

    def start(self): ...                   # spawn 3 threads
    def send_cmd(self, verb, data=None, timeout=2.0) -> dict | None: ...
    def link_alive(self) -> bool:
        return self._connected.is_set() and (time.monotonic() - self._last_rx) < 30.0
```

### 6.3 RX thread

```
while not shutdown:
    if self._ser is None:
        self._reconnect()                  # backoff 1→2→5→10→30s
        continue
    try:
        line = self._ser.readline()         # timeout 1s
    except SerialException:
        self._ser = None
        self._connected.clear()
        continue
    if not line:                            # timeout
        continue
    try:
        msg = protocol.decode(line)
    except ProtocolError as e:
        log.warning("malformed: %r (%s)", line, e)
        continue
    self._last_rx = time.monotonic()
    self._dispatch(msg)
```

`_dispatch`:
- `type=ack` → look up `_pending[id]`, set result, signal.
- `type=evt, v=log` → insert into `esp_log` table.
- `type=evt, v=boot` → log info, optionally re-send `cmd:config` for re-sync.
- `type=evt, v=rfid` → insert `events(method='rfid', user_id=lookup_by_name(data.name), granted=(result=='granted'), detail=json(data))`; trigger recorder.
- `type=evt, v=gate | person_passed | heartbeat` → push `EspEvent(v, data)` to EventBus for any Flask consumer.

### 6.4 TX thread

```
while not shutdown:
    item = self._tx_queue.get(timeout=0.5)
    if item is SHUTDOWN_SENTINEL: break
    msg_id, payload, ack_event, ack_holder = item
    with self._port_lock:
        if self._ser is None:
            if ack_event:
                ack_holder['err'] = LinkDown()
                ack_event.set()
            continue
        try:
            self._ser.write(payload)
        except SerialException:
            self._ser = None
            if ack_event:
                ack_holder['err'] = LinkDown()
                ack_event.set()
            continue
    if ack_event:
        with self._pending_lock:
            self._pending[msg_id] = (ack_event, ack_holder)
        # ack_holder cleaned up either by RX dispatch or by a 2s timeout in send_cmd
```

### 6.5 Heartbeat thread

```
while not self._shutdown.wait(self._ping_interval):
    if not self._connected.is_set():
        continue
    try:
        self.send_cmd("ping", timeout=2.0)
    except LinkDown:
        pass
    if not self.link_alive():
        log.warning("link silent > 30s")
```

### 6.6 `send_cmd` flow

```python
def send_cmd(self, verb, data=None, timeout=2.0) -> dict | None:
    msg_id = next(self._next_id)
    payload = protocol.encode("cmd", verb, data, msg_id)
    ack_event = threading.Event()
    ack_holder = {}
    self._tx_queue.put((msg_id, payload, ack_event, ack_holder))
    if not ack_event.wait(timeout):
        with self._pending_lock:
            self._pending.pop(msg_id, None)
        raise LinkTimeout(f"no ack for {verb} id={msg_id}")
    if 'err' in ack_holder:
        raise ack_holder['err']
    return ack_holder.get('data')
```

### 6.7 Flashing ESP32

Stop systemd before flashing:

```
sudo systemctl stop smart-gate
esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 921600 write_flash 0x0 firmware.bin
sudo systemctl start smart-gate
```

Documented in README. The daemon makes no attempt to coexist with flashing.

---

## 7. Recorder (`video/recorder.py`)

### 7.1 Ring buffer

```python
class RingBuffer:
    def __init__(self, fps=15, pre_seconds=5):
        self._cap = fps * pre_seconds
        self._buf = collections.deque(maxlen=self._cap)
        self._lock = threading.Lock()
    def push(self, jpeg, ts_mono):
        with self._lock:
            self._buf.append((ts_mono, jpeg))
    def snapshot(self):
        with self._lock:
            return list(self._buf)
```

### 7.2 Recording flow

The ring buffer is fed by the `cap` thread (`ring.push(jpeg, time.monotonic())` after each `hub.publish()`), not by a separate consumer — avoids adding a thread and avoids the recorder thread blocking the ring feed while ffmpeg runs.

```python
def run(hub, ring, trigger_queue, db, cfg, shutdown):
    # This thread only waits on trigger_queue; ring is fed by cap thread.
    while not shutdown.is_set():
        try:
            trig = trigger_queue.get(timeout=0.5)
        except queue.Empty:
            continue
        _record_one(trig, hub, ring, db, cfg)

def _record_one(trig, hub, ring, db, cfg):
    if shutil.disk_usage(cfg.data_dir).free < 200 * 1024 * 1024:
        log.error("disk full, skipping clip for event %d", trig.event_id)
        return
    pre_frames = ring.snapshot()
    post_frames = []
    deadline = time.monotonic() + cfg.post_seconds
    while time.monotonic() < deadline and not shutdown.is_set():
        jpg = hub.wait_jpeg(timeout=0.5)
        if jpg is None: continue
        post_frames.append((time.monotonic(), jpg))
    with tempfile.TemporaryDirectory(dir=cfg.data_dir) as tmp:
        for i, (_, jpg) in enumerate(pre_frames + post_frames):
            (Path(tmp) / f"{i:05d}.jpg").write_bytes(jpg)
        out = Path(cfg.data_dir) / "clips" / f"{trig.event_id}.mp4"
        cmd = [
            "ffmpeg", "-loglevel", "warning",
            "-framerate", str(cfg.fps),
            "-i", f"{tmp}/%05d.jpg",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
            "-movflags", "+faststart", "-y", str(out),
        ]
        try:
            subprocess.run(cmd, check=True, timeout=cfg.ffmpeg_timeout_s)
            db.update_event_clip(trig.event_id, f"clips/{trig.event_id}.mp4")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            log.warning("ffmpeg failed for event %d: %s", trig.event_id, e)
            out.unlink(missing_ok=True)
```

Single-track: trigger_queue is `queue.Queue(maxsize=5)`. Overflow → drop new triggers with WARN.

### 7.3 Cleanup thread

Runs at startup +30 s and every 1 h.

```python
def cleanup_pass(data_dir, db, max_age_days, max_total_gb):
    cutoff_ts = (datetime.now() - timedelta(days=max_age_days)).isoformat()
    rows = db.query("SELECT id, clip_path, ts FROM events WHERE clip_path IS NOT NULL ORDER BY ts ASC")
    # Phase 1: age
    for r in list(rows):
        if r.ts < cutoff_ts:
            _delete_clip(data_dir, r, db)
            rows.remove(r)
    # Phase 2: size
    remaining = [(r, (data_dir / r.clip_path).stat().st_size) for r in rows if (data_dir / r.clip_path).exists()]
    total = sum(sz for _, sz in remaining)
    limit = max_total_gb * 1024**3
    while total > limit and remaining:
        r, sz = remaining.pop(0)
        _delete_clip(data_dir, r, db)
        total -= sz

def _delete_clip(data_dir, row, db):
    try: (data_dir / row.clip_path).unlink()
    except FileNotFoundError: pass
    db.execute("UPDATE events SET clip_path=NULL WHERE id=?", (row.id,))
```

Event rows are preserved; only the video file and the `clip_path` reference are dropped.

---

## 8. Flask web admin (`web/`)

| Route | Method | Behaviour |
|---|---|---|
| `/` | GET | `dashboard.html` |
| `/stream.mjpeg` | GET | `multipart/x-mixed-replace; boundary=FRAME` generator from `FrameHub.wait_jpeg()` |
| `/events.json` | GET | JSON list of 50 most recent events; query param `after_id` for incremental |
| `/users` | GET | `users.html` table (name, created_at, last_seen, encoding count, QR active y/n) |
| `/clips/<int:event_id>.mp4` | GET | `send_file()` from `data/clips/`; 404 if `clip_path` is NULL |
| `/api/gate/open` | POST | `uart.send_cmd("open", {"user":"admin","reason":"manual"}, 2.0)`; INSERT `events(method='manual_open', user_id=NULL, granted=1)`; 200 or 503 |
| `/api/gate/close` | POST | `uart.send_cmd("close", None, 2.0)`; INSERT `events(method='manual_close', user_id=NULL, granted=1)`; 200 or 503 |
| `/healthz` | GET | `{"uptime_s", "link_alive", "last_frame_ago_s", "threads_ok"}` |

Templates use Jinja2; HTMX (`/static/htmx.min.js`) polls `/events.json` every 2 s. Pico.css (`/static/pico.min.css`) for cosmetic baseline. No JS framework. No auth (LAN-only deployment per architecture decision). Werkzeug threaded server bound `0.0.0.0:8080`; production WSGI server (gunicorn etc.) explicitly out of scope.

### 8.1 Dashboard layout (`dashboard.html`)

```
┌────────────────────────────────┬──────────────────────────────┐
│                                │  Events                       │
│   <img src="/stream.mjpeg">    │  ┌──────┬───────┬────────┐   │
│                                │  │ time │ user  │ method │   │
│                                │  ├──────┼───────┼────────┤   │
│                                │  │ ...  │  ...  │  ...   │   │
│   [ Open gate ] [ Close gate ] │  │ ...  │  ...  │  ...   │   │
│   Link: ● up   Frame: 0.2s ago │  └──────┴───────┴────────┘   │
└────────────────────────────────┴──────────────────────────────┘
```

`hx-get="/events.json" hx-trigger="every 2s" hx-target="#events-tbody"` for the table.

### 8.2 MJPEG generator

```python
def mjpeg_stream():
    while True:
        jpg = hub.wait_jpeg(timeout=2.0)
        if jpg is None:
            jpg = PLACEHOLDER_JPEG  # "Camera offline" pre-rendered ~3 KB
        yield (b"--FRAME\r\nContent-Type: image/jpeg\r\n"
               b"Content-Length: " + str(len(jpg)).encode() + b"\r\n\r\n"
               + jpg + b"\r\n")
```

---

## 9. CLI (`cli/`)

`python -m smart_gate.cli <subcommand> [args]`. Uses `argparse` (stdlib, no Click dep).

| Subcommand | Effect |
|---|---|
| `enroll --name <X> [--samples 5] [--camera 0]` | Open cv2 capture, show preview window, prompt SPACE to capture each sample, compute embeddings, INSERT user + face_encodings, generate 16-byte hex QR token, write `data/qr/<X>.png`, signal daemon. |
| `users list` | Print table: id, name, created_at, last_seen, #encodings, #active_qr. |
| `users delete --name <X>` | DELETE FROM users WHERE name=? (CASCADE), signal daemon. |
| `qr rotate --name <X>` | Tx: UPDATE qr_tokens SET revoked_at=now() WHERE user_id=? AND revoked_at IS NULL; INSERT new token; rewrite PNG; signal daemon. |
| `qr revoke --name <X>` | UPDATE qr_tokens SET revoked_at=now() WHERE …; signal daemon. |
| `events tail [-n 20]` | SELECT ... ORDER BY ts DESC LIMIT N, pretty-print. |
| `db migrate` | Apply migrations idempotently. |

### 9.1 Daemon reload via SIGUSR1

```python
# cli/_signal.py
def signal_daemon():
    pid_file = Path("/run/smart-gate/pid")
    if not pid_file.exists():
        print("daemon not running; matcher will load fresh on next start")
        return
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, signal.SIGUSR1)
    except (ProcessLookupError, PermissionError) as e:
        print(f"could not signal daemon: {e}")
```

Daemon sets `reload_event` in handler; detector loop calls `matcher.reload(db)` at next iteration.

### 9.2 Enrollment sample capture

```python
def capture_samples(name, n_samples, camera_index):
    cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    mp_det = mp.solutions.face_detection.FaceDetection(min_detection_confidence=0.7)
    encs = []
    cv2.namedWindow("enroll")
    while len(encs) < n_samples:
        ok, frame = cap.read()
        if not ok: continue
        # draw bbox if face detected; show instructions
        cv2.imshow("enroll", annotated)
        k = cv2.waitKey(30) & 0xFF
        if k == 27: break          # ESC abort
        if k == 32:                # SPACE capture
            enc = compute_encoding(frame, mp_det)
            if enc is None:
                print("no face detected, try again")
                continue
            encs.append(enc)
            print(f"captured {len(encs)}/{n_samples}")
    cap.release()
    cv2.destroyAllWindows()
    return encs
```

---

## 10. Configuration (`config.py`)

`tomllib` (Python 3.11 stdlib). Default location `/etc/smart-gate/config.toml`, override via `--config /path`. Schema:

```toml
[video]
camera_index    = 0
width           = 640
height          = 480
fps             = 15

[recognition]
face_threshold        = 0.55
uncertain_band        = [0.55, 0.65]
auth_cooldown_s       = 5
stranger_cooldown_s   = 30
mediapipe_min_conf    = 0.6
face_samples_per_user = 5

[link]
port                  = "/dev/ttyUSB0"
baud                  = 115200
ping_interval_s       = 5
heartbeat_timeout_s   = 30

[recorder]
pre_seconds         = 5
post_seconds        = 5
max_age_days        = 30
max_total_gb        = 5
ffmpeg_timeout_s    = 30

[web]
host = "0.0.0.0"
port = 8080

[paths]
data_dir = "/var/lib/smart-gate"
log_dir  = "/var/log/smart-gate"

[logging]
level         = "INFO"
rotate_mb     = 50
backup_count  = 5
```

`config.py` exposes a frozen dataclass `Config` (one section = one nested dataclass) so consumers get attribute access (`cfg.recognition.face_threshold`) with IDE completion. Loader fills missing fields from defaults baked into the dataclass; unknown TOML keys raise.

---

## 11. Logging

Python `logging`, configured once in `main.py`. Format:

```
%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s
```

Two handlers:

- `RotatingFileHandler` → `/var/log/smart-gate/app.log`, 50 MB × 5 backups.
- `StreamHandler` → stdout (systemd journal captures).

Level: `INFO` default, `DEBUG` when env var `SMART_GATE_DEBUG=1` set (`Environment=SMART_GATE_DEBUG=1` in unit file if needed). Module loggers: `smart_gate.video.capture`, `smart_gate.recognition.detector`, etc., letting `journalctl -u smart-gate -t smart_gate.link.uart_client` filter.

---

## 12. systemd unit (`packaging/smart-gate.service`)

```ini
[Unit]
Description=Smart Gate daemon (Pi 5 side)
After=network.target dev-ttyUSB0.device
Wants=network.target

[Service]
Type=simple
User=smart-gate
Group=smart-gate
SupplementaryGroups=video dialout
WorkingDirectory=/opt/smart-gate
ExecStart=/opt/smart-gate/.venv/bin/python -m smart_gate
Restart=on-failure
RestartSec=3
PIDFile=/run/smart-gate/pid
RuntimeDirectory=smart-gate
StateDirectory=smart-gate
LogsDirectory=smart-gate
StandardOutput=journal
StandardError=journal
# Allow CAP_NET_BIND_SERVICE not needed (port 8080 unprivileged)
# Allow SIGUSR1 reload via 'kill' from the smart-gate group:
PermissionsStartOnly=true

[Install]
WantedBy=multi-user.target
```

The daemon writes its PID into `/run/smart-gate/pid` on startup (provided by `RuntimeDirectory=`).

---

## 13. Installation (`scripts/install.sh`)

Idempotent install for Raspberry Pi OS Bookworm 64-bit:

```bash
#!/usr/bin/env bash
set -euo pipefail

# System packages (apt — Bookworm has all of these)
sudo apt update
sudo apt install -y \
    python3 python3-venv \
    python3-opencv python3-dlib python3-mediapipe \
    libzbar0 ffmpeg sqlite3 \
    v4l-utils

# User + dirs
sudo adduser --system --group --no-create-home smart-gate || true
sudo usermod -aG video,dialout smart-gate
sudo install -d -o smart-gate -g smart-gate \
    /opt/smart-gate \
    /etc/smart-gate \
    /var/lib/smart-gate \
    /var/lib/smart-gate/clips \
    /var/lib/smart-gate/qr \
    /var/log/smart-gate

# Code
sudo rsync -a --delete \
    --exclude=.git --exclude=tests --exclude=__pycache__ \
    ./ /opt/smart-gate/

# Venv (with --system-site-packages so apt-installed opencv/dlib/mediapipe are visible)
sudo python3 -m venv --system-site-packages /opt/smart-gate/.venv
sudo /opt/smart-gate/.venv/bin/pip install --upgrade pip
sudo /opt/smart-gate/.venv/bin/pip install -r /opt/smart-gate/requirements.txt
sudo chown -R smart-gate:smart-gate /opt/smart-gate

# Config (don't overwrite existing)
if [ ! -f /etc/smart-gate/config.toml ]; then
    sudo install -o smart-gate -g smart-gate -m 0644 \
        packaging/config.default.toml /etc/smart-gate/config.toml
fi

# systemd
sudo install -m 0644 packaging/smart-gate.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now smart-gate

# Run initial DB migration as the service user
sudo -u smart-gate /opt/smart-gate/.venv/bin/python -m smart_gate.cli db migrate
```

### 13.1 `requirements.txt`

```
pyserial==3.5
face_recognition==1.3.0
pyzbar==0.1.9
qrcode[pil]==7.4.2
flask==3.0.3
jinja2==3.1.4
numpy>=1.24,<2.0
```

`opencv-python`, `dlib`, `mediapipe` deliberately NOT in `requirements.txt` — they come from apt + `--system-site-packages` to avoid hour-long ARM wheel builds.

---

## 14. Tests

### 14.1 Unit (`tests/unit/`)

| File | Coverage |
|---|---|
| `test_protocol.py` | `encode/decode` happy path, malformed JSON, > MAX_LINE, missing required fields, unknown type, ack with id, event without id. ~12 tests. |
| `test_matcher.py` | Empty index; single user single sample; multi-sample min-distance; threshold edge; identical embeddings; reload picks up new row. ~6 tests. |
| `test_recorder.py` | `cleanup_pass` age-only path; size-only path; hybrid (age + size); empty events; disk-full skip. ~5 tests. |
| `test_db.py` | Migration runs idempotently; user+encoding+qr insert; CASCADE on user delete; partial-unique enforces one active QR; event row preserves user_id NULL on user delete (SET NULL). ~6 tests. |
| `test_config.py` | Defaults applied; TOML override merges; unknown key raises; type validation. ~4 tests. |

Total ~33 unit tests. Run: `pytest tests/unit/ -q`. Target: green on dev machine without hardware.

### 14.2 Integration (`tests/integration/`)

Mocks:

- `mocks/serial.py` — `FakeSerial` with `write` capturing bytes and `readline` returning scripted lines per scenario (boot → heartbeat sequence; ack to cmd:open; malformed line; SerialException injection).
- `mocks/camera.py` — `FakeVideoCapture` reading JPEGs from `tests/integration/fixtures/frames/` in a loop.

Scenarios in `test_pipeline.py`:

1. Boot → daemon connects, sees `evt:boot`, sends optional `cmd:config`.
2. Authorized face: fixture frame contains known face → detector emits AuthEvent → uart sends `cmd:open` with correct verb+data; ack received; event row inserted with `method='face' granted=1`.
3. Stranger face: unknown face → granted=0 event; no `cmd:open` sent.
4. RFID inbound: scripted `evt:rfid granted=alice` → `events` row inserted with `method='rfid' granted=1`; recorder triggered.
5. QR scan: fixture QR fixture frame → matcher.lookup_qr → emit grant.
6. Link down: `FakeSerial` raises SerialException → uart reconnect loop; `/api/gate/open` returns 503.
7. Debouncer: two face detections within 5 s → only one `cmd:open`, only one event row.
8. CLI enroll + SIGUSR1: simulate CLI enroll path writing DB → send SIGUSR1 → matcher reloads and matches new user on next frame.

Each scenario asserts on: `db.events`, `FakeSerial.written`, log messages. ~10 integration tests.

### 14.3 No CI

Per scope B. README documents `pytest tests/` as the test runner. Pre-demo manual smoke test on physical hardware also covered by README.

---

## 15. Out of scope (deferred)

- Multi-face per frame (queue / sequential match).
- Live face enroll from the Flask UI (browser webcam capture).
- Authentication on the Flask admin (LAN-only assumption).
- Gunicorn / production WSGI.
- HTTPS / Let's Encrypt.
- Cloud sync, multi-gate federation, MQTT.
- OTA daemon update mechanism.
- Backup of `data/smart_gate.db` to external storage.
- Internationalisation of CLI prompts and templates.
- Performance characterisation across webcam models.

---

## 16. Open risks

1. **mediapipe import on Pi OS Bookworm.** The `python3-mediapipe` apt package may lag behind the latest MediaPipe. If MediaPipe Face Detection API differs from what the code targets, fall back to pip wheel `mediapipe==0.10.x` (slower install but available).
2. **face_recognition + dlib on `--system-site-packages`.** `apt python3-dlib` exposes the C++ extension; `face_recognition` is a pure-Python wrapper installable from PyPI. If `face_recognition` PyPI wheel forces a dlib install, pin order in `requirements.txt` matters.
3. **Werkzeug streaming under load.** Werkzeug dev server can stall MJPEG when the client disconnects mid-stream; mitigated by `try/except` around the generator's `yield`.
4. **SD card endurance.** Continuous writes (events + clips + WAL) wear cards. For 1–2 week demos this is negligible; longer deployments should use an SSD via USB.
5. **CLI enrollment window manager.** `cv2.imshow` requires X / Wayland session. On Pi OS Lite this would need adaptation (e.g., capture frames headless and write thumbnails to disk for the operator to review). README states "use Pi OS with desktop or run CLI from a remote workstation."

---

*End of design doc.*
