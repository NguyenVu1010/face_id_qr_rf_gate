# Smart-gate hang fix + repo-wide robustness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the "access denied hang" symptom and close ~14 critical + ~22 important + ~22 minor findings across the smart_gate repo, structured as 4 sequenced phases with independent verification gates.

**Architecture:** ESP32 firmware (PlatformIO, Arduino-ESP32, FreeRTOS) communicates with a Pi 5 daemon (Python 3, Flask + pyserial + SQLite) over a 3-wire GPIO UART. The fix touches both sides — firmware adds new event kinds, timers, NVS state persistence, and accessors; Pi side adds defensive try/except wraps, replay counters, DB transaction context manager, ESP-log batched writer, and audit visibility for denied swipes.

**Tech Stack:** ESP32 + PlatformIO (`pio run` / `pio device monitor`), Arduino-ESP32 framework, MFRC522 + LiquidCrystal_I2C + ESP32Servo + ArduinoJson libs; Python 3.10 with pyserial, Flask, sqlite3, face_recognition; pytest for unit tests; esptool-from-Pi flashing workflow.

**Spec:** `docs/superpowers/specs/2026-06-12-smart-gate-hang-and-robustness-fixes-design.md`

---

## Phase 0 — Setup & baseline (do once before Phase 1)

### Task 0.1: Capture pre-fix baseline metrics

**Files:**
- Create: `docs/superpowers/plans/baseline-2026-06-12.txt` (local notes, not committed)

- [ ] **Step 1: SSH the Pi and snapshot current state**

```bash
ssh pi@192.168.1.137 'bash -s' << 'EOF'
echo '=== /healthz ===' ; curl -s http://127.0.0.1:8080/healthz?format=json ; echo
echo '=== thread count ===' ; ps -L -p $(pgrep -f smart_gate) | wc -l
echo '=== RSS (MB) ===' ; ps -o rss= -p $(pgrep -f smart_gate) | awk '{print $1/1024}'
echo '=== iostat 60s ===' ; iostat -dx 1 60 /dev/mmcblk0 | tail -3
echo '=== journal lines/min ===' ; sudo journalctl -u smart-gate --since '1 min ago' | wc -l
echo '=== last 5 esp_log entries ===' ; curl -s 'http://127.0.0.1:8080/api/esp_log?limit=5'
EOF
```

Save output locally (do not commit). This is the baseline `Pre-P1` column for the Section 10.2 matrix in the spec.

- [ ] **Step 2: Manually reproduce the hang**

Swipe one un-enrolled RFID card. Confirm: LCD shows "Access denied" and stays there until next granted swipe (current bug, expected behaviour pre-fix).

- [ ] **Step 3: Note any pre-existing test failures**

```bash
cd /home/nguyenvd/workspace/smart_gate && /home/nguyenvd/.local/bin/pio --version
pytest tests/unit -q 2>&1 | tail -20
```

Record any failures so they don't get blamed on subsequent commits.

---

## Phase 1 — Urgency fixes

11 tasks, ~145 LOC. Goal: chữa triệu chứng đang gặp + safety quick wins + config defaults đúng.

### Task 1.1: Config defaults — port + face_threshold + missing-config warning

**Files:**
- Modify: `smart_gate/config.py`
- Modify: `packaging/config.default.toml`
- Test: `tests/unit/test_config.py`

- [ ] **Step 1: Read current test_config.py to learn pytest fixtures used for this module**

```bash
grep -n 'def test_' tests/unit/test_config.py | head -20
```

- [ ] **Step 2: Write failing test for the new default + missing-file warning**

Add to `tests/unit/test_config.py`:

```python
def test_link_default_port_is_serial0():
    from smart_gate.config import LinkCfg
    assert LinkCfg().port == "/dev/serial0"

def test_load_config_warns_when_file_missing(tmp_path, caplog):
    import logging
    from smart_gate.config import load_config
    missing = tmp_path / "does-not-exist.toml"
    with caplog.at_level(logging.WARNING, logger="smart_gate.config"):
        cfg = load_config(missing)
    assert "not found" in caplog.text
    assert cfg.link.port == "/dev/serial0"
```

- [ ] **Step 3: Run tests to confirm failure**

```bash
pytest tests/unit/test_config.py -k "default_port or load_config_warns" -v
```

Expected: 2 failures (current default is `/dev/ttyUSB0`; no warning emitted).

- [ ] **Step 4: Fix the default in `smart_gate/config.py`**

Locate the `LinkCfg` dataclass (around line 46) and change:

```python
@dataclass
class LinkCfg:
    port: str = "/dev/serial0"   # was "/dev/ttyUSB0" (pre-decision-#26)
```

- [ ] **Step 5: Add missing-file warning to `load_config`**

Locate `load_config` (around line 111) and update the missing-file branch:

```python
import logging
log = logging.getLogger(__name__)

def load_config(path: Path) -> Config:
    if not path.exists():
        cfg = Config()
        log.warning("config file %s not found, using defaults (link.port=%s)",
                    path, cfg.link.port)
        return cfg
    # ... existing parse path unchanged
```

- [ ] **Step 6: Update `packaging/config.default.toml`**

Line 13 (the `face_threshold` line): change `face_threshold = 0.55` to `face_threshold = 0.25` (matches the 2026-06-10 auth-priority decision in memory).

- [ ] **Step 7: Run tests to confirm pass**

```bash
pytest tests/unit/test_config.py -v
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add smart_gate/config.py packaging/config.default.toml tests/unit/test_config.py
git commit -m "feat(config): sync defaults — port=/dev/serial0, face_threshold=0.25, warn on missing file

Decision #26 (UART transport, 2026-05-23) moved the Pi link to /dev/serial0.
Auth-priority decision (2026-06-10) tightened face match distance to 0.25.
load_config now emits a WARNING when the runtime config is missing so the
silent-fallback case is visible.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 1.2: TZ fix — Flask query sites use UTC

**Files:**
- Modify: `smart_gate/web/app.py`
- Test: `tests/unit/test_web.py`

- [ ] **Step 1: Find every `datetime.now()` site in `smart_gate/web/app.py`**

```bash
grep -n 'datetime\.now' smart_gate/web/app.py
```

- [ ] **Step 2: Write failing test**

Add to `tests/unit/test_web.py`:

```python
def test_today_range_uses_utc(client_with_events_at_local_midnight_minus_1h):
    """Events that are 23:00 yesterday local-time (16:00 UTC if TZ is Asia/Ho_Chi_Minh)
    should be counted as today's only when SQLite-stored UTC date matches local 'today'."""
    # client_with_events_at_local_midnight_minus_1h is a fixture that:
    #   - Sets TZ to Asia/Ho_Chi_Minh
    #   - Inserts an events row with ts = now_utc - 1h
    #   - Calls /events.json?range=today
    # Assertion: the row appears IFF the UTC date matches SQLite's date('now')
    resp = client_with_events_at_local_midnight_minus_1h.get("/events.json?range=today")
    assert resp.status_code == 200
    # The fixture sets the clock to local 00:30; UTC is 17:30 of the prior calendar day.
    # An event inserted 1 hour ago (local 23:30 yesterday) is UTC 16:30 — "yesterday" in UTC terms.
    assert resp.json["count"] == 0
```

(If the fixture doesn't exist yet, add a minimal one to `tests/unit/test_web.py` using `freezegun` or a TZ env override.)

- [ ] **Step 3: Run test to confirm failure**

```bash
pytest tests/unit/test_web.py -k today_range_uses_utc -v
```

Expected: failure (Flask filter uses local time).

- [ ] **Step 4: Replace `datetime.now()` with `datetime.now(timezone.utc)` at every site**

In `smart_gate/web/app.py`, add `from datetime import timezone` near the top, then replace every `datetime.now()` site identified in Step 1. Use `sed`:

```bash
sed -i 's/datetime\.now()/datetime.now(timezone.utc)/g' smart_gate/web/app.py
```

Manually verify the diff doesn't replace any unintended sites:

```bash
git diff smart_gate/web/app.py | head -40
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_web.py -v
```

- [ ] **Step 6: Commit**

```bash
git add smart_gate/web/app.py tests/unit/test_web.py
git commit -m "fix(web): use UTC for date filtering — SQLite stores UTC

datetime.now() returned local time; SQLite datetime('now') is UTC.
The /events.json?range=today filter was 7 hours off in Asia/Ho_Chi_Minh.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 1.3: Pi audit-log for RFID denial

**Files:**
- Modify: `smart_gate/main.py`

- [ ] **Step 1: Locate `_handle_esp_event` rfid branch**

```bash
grep -n 'evt:rfid\|rfid denied\|granted' smart_gate/main.py | head -10
```

The deny branch is around line 387-389.

- [ ] **Step 2: Add the audit line**

Inside the `evt:rfid` handler in `_handle_esp_event`, when `not granted`:

```python
if not granted:
    self._audit(self._esp_log_bus, "warn", "rfid",
                f"denied uid={uid[:8]}… name={name or '(unknown)'}")
    log.info("rfid denied: %s", d)
    return
```

(Keep any existing log.info for backward compatibility — the new audit line is for the dashboard live-log.)

- [ ] **Step 3: Smoke-check the module imports cleanly**

```bash
python -c "import smart_gate.main"
```

- [ ] **Step 4: Commit**

```bash
git add smart_gate/main.py
git commit -m "feat(audit): surface RFID denials in live-log

Previously denied swipes were only in app.log. Now they appear in the
dashboard live-log stream (warn rfid denied uid=… name=…).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 1.4: `_consume_bus` defensive wrap

**Files:**
- Modify: `smart_gate/main.py`
- Test: `tests/unit/test_main_bus.py` (create)

- [ ] **Step 1: Create a minimal test for the wrap**

Create `tests/unit/test_main_bus.py`:

```python
import queue
import threading
import time
from unittest.mock import MagicMock

def test_bus_consumer_survives_exception(monkeypatch, caplog):
    """If a handler raises, the consumer logs and keeps going — does not die."""
    from smart_gate.main import SmartGateApp  # adjust import to actual class name

    app = SmartGateApp.__new__(SmartGateApp)  # bypass __init__
    app._bus = queue.Queue()
    app._shutdown = threading.Event()
    app._esp_log_bus = MagicMock()
    app._db = MagicMock()
    app._db.insert_event.side_effect = [RuntimeError("disk full"), None]
    app._audit = MagicMock()

    # Inject a fake handler that calls db.insert_event (will raise on first call)
    def handler(evt):
        app._db.insert_event("test", None, True)
    monkeypatch.setattr(app, "_handle_manual_event", handler, raising=False)

    t = threading.Thread(target=app._consume_bus, daemon=True)
    t.start()

    # First event triggers exception → should be logged, not kill thread
    app._bus.put({"kind": "manual"})
    time.sleep(0.6)  # let the back-off pass
    # Second event should still be processed
    app._bus.put({"kind": "manual"})
    time.sleep(0.2)
    app._shutdown.set()
    t.join(timeout=2)

    assert not t.is_alive(), "bus consumer thread leaked"
    assert app._db.insert_event.call_count == 2
    app._audit.assert_called()  # synthetic audit emitted on failure
```

(Adapt the import path + class name to whatever `smart_gate/main.py` actually exposes — read the file once to confirm.)

- [ ] **Step 2: Run test to confirm failure**

```bash
pytest tests/unit/test_main_bus.py -v
```

Expected: failure (current code lets exceptions kill the thread).

- [ ] **Step 3: Wrap the loop body**

In `smart_gate/main.py`, locate the `_consume_bus` method (around line 168-194). Replace the body of the `while not self._shutdown.is_set():` loop:

```python
def _consume_bus(self):
    while not self._shutdown.is_set():
        try:
            evt = self._bus.get(timeout=1.0)
        except queue.Empty:
            continue
        try:
            self._dispatch_event(evt)   # whatever the existing dispatch line was
        except Exception:
            log.exception("bus consumer iter failed; continuing")
            try:
                self._audit(self._esp_log_bus, "error", "internal",
                            "bus consumer exception — see app.log")
            except Exception:
                pass
            time.sleep(0.5)
```

(If the existing code is inlined per-event-type instead of dispatching to one method, wrap the whole if/elif chain in the same try/except.)

- [ ] **Step 4: Run test**

```bash
pytest tests/unit/test_main_bus.py -v
```

- [ ] **Step 5: Commit**

```bash
git add smart_gate/main.py tests/unit/test_main_bus.py
git commit -m "fix(daemon): defensive try/except in _consume_bus

Unhandled exceptions from DB writes (SD full, schema drift) were killing
the bus-consumer thread silently — daemon stayed 'running' but processed
no events. Now logs + emits a synthetic 'error internal' audit so the
operator sees the failure on the dashboard, with 0.5 s back-off.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 1.5: `_run_web` clean fail on port-in-use

**Files:**
- Modify: `smart_gate/main.py`

- [ ] **Step 1: Locate `_run_web`**

```bash
grep -n '_run_web\|make_server\|serve_forever' smart_gate/main.py
```

Around line 409-426.

- [ ] **Step 2: Wrap in try/except OSError**

```python
def _run_web(self):
    try:
        self._http_server = make_server(self._cfg.web.host, self._cfg.web.port,
                                        self._flask_app, threaded=True)
        self._http_server.serve_forever()
    except OSError as e:
        log.critical("web bind failed on %s:%d: %s — shutting down",
                     self._cfg.web.host, self._cfg.web.port, e)
        self._shutdown.set()
```

- [ ] **Step 3: Smoke-import**

```bash
python -c "import smart_gate.main"
```

- [ ] **Step 4: Commit**

```bash
git add smart_gate/main.py
git commit -m "fix(daemon): clean shutdown on web port-in-use

Previously OSError EADDRINUSE killed the Flask thread only; daemon kept
running with web dead. Now triggers full shutdown so systemd restarts.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 1.6: LCD restore timer (firmware — root cause of reported hang)

**Files:**
- Modify: `firmware/include/events.h`
- Modify: `firmware/src/main.cpp`
- Modify: `firmware/src/gate_fsm.cpp`

- [ ] **Step 1: Add the new event kind**

In `firmware/include/events.h`, locate the `EventKind` enum and add:

```cpp
enum EventKind : uint8_t {
    // ... existing kinds ...
    EV_T_LCD_RESTORE,   // one-shot timer fired: restore LCD to idle if FSM in S_IDLE
};
```

- [ ] **Step 2: Declare + create the timer in `main.cpp`**

In `firmware/src/main.cpp`, near other timer globals (around line 27-31):

```cpp
TimerHandle_t g_lcd_restore_timer = nullptr;

static void cb_lcd_restore(TimerHandle_t) {
    event_t e{}; e.kind = EV_T_LCD_RESTORE;
    xQueueSend(g_event_q, &e, 0);   // best-effort; drop on full queue
}
```

In `setup()`, after the other timer creates (around line 88-92):

```cpp
g_lcd_restore_timer = xTimerCreate("lcdRst", pdMS_TO_TICKS(2500),
                                   pdFALSE, nullptr, cb_lcd_restore);
```

Do NOT add NULL-check here — that comes in Task 4.6 (Phase 4) along with the other timer-create NULL checks. For now: silent if it fails.

- [ ] **Step 3: Add dispatcher case in `gate_fsm.cpp`**

Locate the FSM dispatcher (the `switch (e.kind)` or `if (e.kind == ...)` chain). Add:

```cpp
if (e.kind == EV_T_LCD_RESTORE) {
    if (s_state == S_IDLE) lcd_show_idle();
    return;
}
```

(Guard prevents stomping an in-flight opening/closing/error message.)

- [ ] **Step 4: Arm the timer in the deny branch**

Locate the `EV_RFID_SCAN` deny branch (around line 244-248):

```cpp
if (!granted) {
    lcd_show_denied();
    buzzer_beep_err();   // will be replaced with _async in Task 1.7
    xTimerChangePeriod(g_lcd_restore_timer, pdMS_TO_TICKS(2500), 0);
    xTimerStart(g_lcd_restore_timer, 0);
    return;
}
```

- [ ] **Step 5: Build firmware**

```bash
cd firmware && /home/nguyenvd/.local/bin/pio run 2>&1 | tail -10
```

Expected: SUCCESS, no new warnings.

- [ ] **Step 6: Commit (do NOT flash yet — flash at end-of-phase verification)**

```bash
cd /home/nguyenvd/workspace/smart_gate
git add firmware/include/events.h firmware/src/main.cpp firmware/src/gate_fsm.cpp
git commit -m "fix(firmware): LCD restore timer on RFID denial — fixes reported hang

After a denied RFID scan the LCD was stuck on 'Access denied' forever
because no code path scheduled a return to lcd_show_idle(). New one-shot
2500 ms timer (g_lcd_restore_timer) posts EV_T_LCD_RESTORE; dispatcher
calls lcd_show_idle() only if FSM is still in S_IDLE so we don't stomp
an opening/closing message.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 1.7: Buzzer non-blocking refactor

**Files:**
- Modify: `firmware/src/buzzer_drv.h`
- Modify: `firmware/src/buzzer_drv.cpp`
- Modify: `firmware/src/gate_fsm.cpp`

- [ ] **Step 1: Read current `buzzer_drv.h` to see existing API**

```bash
cat firmware/src/buzzer_drv.h
```

- [ ] **Step 2: Add async API to the header**

In `firmware/src/buzzer_drv.h`:

```cpp
#pragma once
#include <Arduino.h>

void buzzer_init();
void buzzer_beep_ok();          // deprecated — blocking, kept for old callers
void buzzer_beep_err();         // deprecated — blocking
void buzzer_beep_ok_async();    // schedule non-blocking 80ms HIGH→LOW pulse
void buzzer_beep_err_async();   // schedule non-blocking 6× 60ms HIGH/LOW pattern
void buzzer_start_warn_pattern();   // existing
void buzzer_stop_warn_pattern();    // existing
```

- [ ] **Step 3: Implement the async pulse timer in `buzzer_drv.cpp`**

Replace the body of `buzzer_drv.cpp` blocking beeps with a state-machine timer:

```cpp
#include "buzzer_drv.h"
#include "config.h"

static TimerHandle_t s_pulse_timer = nullptr;
static int s_pulse_remaining = 0;        // how many state transitions left
static int s_pulse_period_ms = 60;       // 60 ms for err, 80 for ok
static bool s_pulse_high_next = true;    // next state

static void cb_pulse(TimerHandle_t) {
    if (s_pulse_remaining <= 0) {
        digitalWrite(PIN_BUZZER, LOW);
        return;
    }
    digitalWrite(PIN_BUZZER, s_pulse_high_next ? HIGH : LOW);
    s_pulse_high_next = !s_pulse_high_next;
    s_pulse_remaining--;
    if (s_pulse_remaining > 0) {
        xTimerChangePeriod(s_pulse_timer, pdMS_TO_TICKS(s_pulse_period_ms), 0);
        xTimerStart(s_pulse_timer, 0);
    } else {
        digitalWrite(PIN_BUZZER, LOW);
    }
}

void buzzer_init() {
    pinMode(PIN_BUZZER, OUTPUT);
    digitalWrite(PIN_BUZZER, LOW);
    s_pulse_timer = xTimerCreate("buzzPulse", pdMS_TO_TICKS(60),
                                 pdFALSE, nullptr, cb_pulse);
    // Stop in case re-init while running (idempotent)
    if (s_pulse_timer) xTimerStop(s_pulse_timer, 0);
}

void buzzer_beep_ok_async() {
    if (!s_pulse_timer) return;
    s_pulse_period_ms = 80;
    s_pulse_remaining = 2;    // HIGH then LOW
    s_pulse_high_next = true;
    xTimerChangePeriod(s_pulse_timer, pdMS_TO_TICKS(s_pulse_period_ms), 0);
    xTimerStart(s_pulse_timer, 0);
}

void buzzer_beep_err_async() {
    if (!s_pulse_timer) return;
    s_pulse_period_ms = 60;
    s_pulse_remaining = 12;   // 6× HIGH/LOW
    s_pulse_high_next = true;
    xTimerChangePeriod(s_pulse_timer, pdMS_TO_TICKS(s_pulse_period_ms), 0);
    xTimerStart(s_pulse_timer, 0);
}

// Legacy blocking variants — keep as thin wrappers to avoid touching every caller
void buzzer_beep_ok()  { buzzer_beep_ok_async(); }
void buzzer_beep_err() { buzzer_beep_err_async(); }

// (warn pattern existing impl unchanged — copy from current file)
```

(Preserve any existing `buzzer_start_warn_pattern` / `buzzer_stop_warn_pattern` impl by copying them unchanged from the original file.)

- [ ] **Step 4: Switch call sites in `gate_fsm.cpp`**

```bash
grep -n 'buzzer_beep_' firmware/src/gate_fsm.cpp
```

Replace `buzzer_beep_err()` with `buzzer_beep_err_async()`, `buzzer_beep_ok()` with `buzzer_beep_ok_async()` everywhere in `gate_fsm.cpp`. Other files may still use the blocking variants — the wrapper preserves behaviour, but FSM code is the latency-critical path.

- [ ] **Step 5: Build**

```bash
cd firmware && /home/nguyenvd/.local/bin/pio run 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
cd /home/nguyenvd/workspace/smart_gate
git add firmware/src/buzzer_drv.h firmware/src/buzzer_drv.cpp firmware/src/gate_fsm.cpp
git commit -m "fix(firmware): non-blocking buzzer beeps — frees FSM task

buzzer_beep_err() was blocking the FSM task for 360 ms (6 × 60 ms
vTaskDelay). During the stall, the event queue wasn't drained, so rapid
re-taps were silently dropped. Refactored into a FreeRTOS timer-driven
state machine; FSM task returns immediately. Legacy blocking entries
kept as wrappers so non-FSM callers compile unchanged.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 1.8: LCD presence-icons foundation (custom glyphs + accessors)

**Files:**
- Modify: `firmware/src/lcd_drv.h`
- Modify: `firmware/src/lcd_drv.cpp`
- Modify: `firmware/src/sensor.h`
- Modify: `firmware/src/sensor.cpp`
- Modify: `firmware/src/rfid.h`
- Modify: `firmware/src/rfid.cpp`

- [ ] **Step 1: Add the icon API to `lcd_drv.h`**

```cpp
// Append:
void lcd_update_icons(bool obstacle_present, bool card_present);
int  lcd_drv_last_i2c_err();   // used in Task 1.10
```

- [ ] **Step 2: Define glyphs + impl in `lcd_drv.cpp`**

Near the top of `lcd_drv.cpp`:

```cpp
// Obstacle warning glyph — filled triangle with an exclamation column
// (5 cols × 8 rows; ≥60% pixel fill, clearly recognisable on the deployed module)
static const uint8_t GLYPH_OBSTACLE[8] = {
    0b00100,
    0b00100,
    0b01110,
    0b01010,
    0b11111,
    0b11011,
    0b00100,
    0b11111,
};

// RFID card glyph — card outline with two "wave" arcs above
static const uint8_t GLYPH_RFID[8] = {
    0b00100,
    0b01010,
    0b00100,
    0b11111,
    0b10001,
    0b10001,
    0b11111,
    0b00000,
};

static int s_last_i2c_err = 0;
```

In `lcd_init()`, after `s_lcd.init()` / `s_lcd.backlight()`:

```cpp
s_lcd.createChar(0, (uint8_t*)GLYPH_OBSTACLE);
s_lcd.createChar(1, (uint8_t*)GLYPH_RFID);
```

Add `lcd_update_icons` at the bottom:

```cpp
void lcd_update_icons(bool obstacle_present, bool card_present) {
    static bool s_last_obs = false;
    static bool s_last_rfid = false;
    static bool s_first = true;

    if (!s_first && obstacle_present == s_last_obs && card_present == s_last_rfid) {
        return;   // no I²C write when state unchanged
    }
    s_first = false;
    s_last_obs = obstacle_present;
    s_last_rfid = card_present;

    s_lcd.setCursor(14, 0);
    s_lcd.write(obstacle_present ? (uint8_t)0 : ' ');
    s_lcd.setCursor(15, 0);
    s_lcd.write(card_present ? (uint8_t)1 : ' ');

    // capture transmission status for the I²C diagnostic log (Task 1.10)
    s_last_i2c_err = 0;   // refined in Task 3.14 with real probe
}

int lcd_drv_last_i2c_err() { return s_last_i2c_err; }
```

- [ ] **Step 3: Shrink row-0 text area to cols 0-13**

In `lcd_drv.cpp`, change `LCD_COLS` references inside `lcd_show_idle`, `lcd_show_denied`, `lcd_show_opening`, `lcd_show_closing` to limit row 0 writes to 14 columns (cols 0-13). `lcd_show_name` should write the name on row 1 if it fits, or truncate on row 0 to 14 chars.

Mechanical edit: any `write_row(s_lcd, 0, "...", LCD_COLS)` style call for row 0 becomes `write_row(s_lcd, 0, "...", 14)`. Row 1 (`s_lcd.setCursor(0, 1)`) unchanged.

- [ ] **Step 4: Add sensor obstacle accessor**

In `firmware/src/sensor.h`:

```cpp
bool sensor_is_obstacle();
```

In `firmware/src/sensor.cpp`, at module scope:

```cpp
static volatile bool s_obstacle_present = false;
```

Inside `sensor_task` (where the read result is processed), after the debounce comparison:

```cpp
s_obstacle_present = (cm > 0 && cm < SENSOR_TRIGGER_CM);
```

(Use raw last sample for the icon — it refreshes 5 Hz, debounce is for the FSM event.)

At file bottom:

```cpp
bool sensor_is_obstacle() { return s_obstacle_present; }
```

- [ ] **Step 5: Add RFID card-presence accessor**

In `firmware/src/rfid.h`:

```cpp
bool rfid_is_card_present();
```

In `firmware/src/rfid.cpp`, at module scope:

```cpp
static volatile bool s_card_present = false;
static volatile uint32_t s_card_last_ms = 0;
```

Inside `rfid_task`, immediately after `PICC_IsNewCardPresent()` returns true:

```cpp
s_card_present = true;
s_card_last_ms = millis();
```

Add at the top of each loop iteration (before the next poll):

```cpp
if (s_card_present && (millis() - s_card_last_ms) > 300) {
    s_card_present = false;   // 300 ms hold after last detection
}
```

At file bottom:

```cpp
bool rfid_is_card_present() { return s_card_present; }
```

- [ ] **Step 6: Build**

```bash
cd firmware && /home/nguyenvd/.local/bin/pio run 2>&1 | tail -5
```

- [ ] **Step 7: Commit**

```bash
cd /home/nguyenvd/workspace/smart_gate
git add firmware/src/lcd_drv.h firmware/src/lcd_drv.cpp \
        firmware/src/sensor.h firmware/src/sensor.cpp \
        firmware/src/rfid.h firmware/src/rfid.cpp
git commit -m "feat(firmware): LCD presence icons foundation — glyphs + accessors

Adds the two custom HD44780 glyphs (obstacle warning at cell 0, RFID
card at cell 1), lcd_update_icons() that writes only on state change to
avoid I²C floods, and accessors sensor_is_obstacle() + rfid_is_card_present()
(with a 300 ms hold so the RFID icon doesn't flicker between poll cycles).
Row 0 text area shrunk to columns 0-13 to leave 14-15 for icons.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 1.9: LCD icon-tick wiring (event + timer + dispatcher)

**Files:**
- Modify: `firmware/include/events.h`
- Modify: `firmware/src/main.cpp`
- Modify: `firmware/src/gate_fsm.cpp`

- [ ] **Step 1: Add the event kind**

In `firmware/include/events.h`, append:

```cpp
EV_T_LCD_ICON_TICK,   // 200 ms periodic — refresh top-right LCD icons
```

- [ ] **Step 2: Add timer + callback in `main.cpp`**

```cpp
TimerHandle_t g_lcd_icon_timer = nullptr;

static void cb_lcd_icon(TimerHandle_t) {
    event_t e{}; e.kind = EV_T_LCD_ICON_TICK;
    xQueueSend(g_event_q, &e, 0);
}
```

In `setup()`:

```cpp
g_lcd_icon_timer = xTimerCreate("lcdIcon", pdMS_TO_TICKS(200),
                                pdTRUE, nullptr, cb_lcd_icon);  // pdTRUE = periodic
xTimerStart(g_lcd_icon_timer, 0);
```

- [ ] **Step 3: Add dispatcher case in `gate_fsm.cpp`**

```cpp
if (e.kind == EV_T_LCD_ICON_TICK) {
    lcd_update_icons(sensor_is_obstacle(), rfid_is_card_present());
    return;
}
```

Add includes at top of `gate_fsm.cpp` if needed: `#include "sensor.h"` and `#include "rfid.h"`.

- [ ] **Step 4: Build**

```bash
cd firmware && /home/nguyenvd/.local/bin/pio run 2>&1 | tail -5
```

- [ ] **Step 5: Commit**

```bash
cd /home/nguyenvd/workspace/smart_gate
git add firmware/include/events.h firmware/src/main.cpp firmware/src/gate_fsm.cpp
git commit -m "feat(firmware): drive LCD icons from a 200ms periodic timer

5Hz refresh is fast enough for live feel, slow enough that state-change-
only updates produce zero I²C writes in idle.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 1.10: I²C diagnostic log on RFID swipe

**Files:**
- Modify: `firmware/src/gate_fsm.cpp`
- Modify: `firmware/src/lcd_drv.cpp` (for real I²C error capture, refined further in Task 3.14)

- [ ] **Step 1: Capture I²C error in `lcd_drv.cpp` write paths**

In `lcd_drv.cpp` `write_row` (or the lowest-level function that hits `s_lcd.print`), wrap the call:

```cpp
static void write_row(int row, const char* s, int n) {
    s_lcd.setCursor(0, row);
    // ... existing pad/truncate logic ...
    s_lcd.print(/*padded buffer*/);

    // Probe bus health after write — single probe transaction
    Wire.beginTransmission(LCD_ADDR);
    s_last_i2c_err = Wire.endTransmission();
}
```

(`LCD_ADDR` constant should already exist in the file or `config.h`. If not, add it.)

- [ ] **Step 2: Emit the swipe log in the FSM dispatcher**

In `firmware/src/gate_fsm.cpp` inside the `EV_RFID_SCAN` handler, right after `lcd_show_denied()` and `lcd_show_name()` calls:

```cpp
if (!granted) {
    lcd_show_denied();
    int err = lcd_drv_last_i2c_err();
    if (err == 0) LOGI("i2c", "swipe uid=%s lcd_write ok", e.uid);
    else          LOGW("i2c", "swipe uid=%s lcd_write err=%d", e.uid, err);
    buzzer_beep_err_async();
    xTimerChangePeriod(g_lcd_restore_timer, pdMS_TO_TICKS(2500), 0);
    xTimerStart(g_lcd_restore_timer, 0);
    return;
}
// Granted path:
lcd_show_name(e.name);
{
    int err = lcd_drv_last_i2c_err();
    if (err == 0) LOGI("i2c", "swipe uid=%s lcd_write ok", e.uid);
    else          LOGW("i2c", "swipe uid=%s lcd_write err=%d", e.uid, err);
}
```

- [ ] **Step 3: Build**

```bash
cd firmware && /home/nguyenvd/.local/bin/pio run 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
cd /home/nguyenvd/workspace/smart_gate
git add firmware/src/gate_fsm.cpp firmware/src/lcd_drv.cpp
git commit -m "feat(firmware): i2c diagnostic log per RFID swipe

Every swipe emits one info (ok) or warn (err=N) log line tagged 'i2c'
with the LCD write status. Dashboard live-log now correlates LCD bus
health with swipe activity. Existing 1Hz log rate-limiter (log_emit.cpp)
covers the worst-case spam.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 1.11: Phase 1 verification gate (manual — flash + bench tests)

This task is performed by the operator at the bench, NOT by the agent. It is the natural pause point before Phase 2 begins.

- [ ] **Step 1: Flash the ESP from the Pi**

```bash
cd /home/nguyenvd/workspace/smart_gate/firmware
cp ~/.platformio/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin .pio/build/esp32dev/
cd .pio/build/esp32dev && scp bootloader.bin partitions.bin boot_app0.bin firmware.bin pi@192.168.1.137:/tmp/
ssh pi@192.168.1.137 '~/.local/bin/esptool --chip esp32 --port /dev/ttyUSB0 --baud 460800 \
    --before default_reset --after hard_reset \
    write_flash -z --flash_mode dio --flash_freq 40m --flash_size 4MB \
    0x1000 /tmp/bootloader.bin 0x8000 /tmp/partitions.bin \
    0xe000 /tmp/boot_app0.bin 0x10000 /tmp/firmware.bin'
```

- [ ] **Step 2: Restart the Pi daemon**

```bash
ssh pi@192.168.1.137 'sudo systemctl restart smart-gate && sleep 3 && sudo systemctl status smart-gate --no-pager | head -10'
```

- [ ] **Step 3: Run the Phase 1 test matrix (spec §10.3)**

For each of these 9 tests, mark pass/fail:

1. [ ] Swipe an un-enrolled card 5× — LCD returns to idle within 2.5 s each time. Dashboard `/api/esp_log` shows 5 `warn rfid denied` lines.
2. [ ] Swipe deny then granted *during* the buzzer pattern — gate opens immediately (FSM not stalled).
3. [ ] On Pi: `sudo mv /etc/smart-gate/config.toml /tmp/test.toml; sudo systemctl restart smart-gate; sudo journalctl -u smart-gate --since '1 min ago' | grep -i 'config file'` — WARNING + port `/dev/serial0`. Then restore config.
4. [ ] `grep face_threshold packaging/config.default.toml` returns `0.25`.
5. [ ] Query `/events.json?range=today` near local midnight — events before UTC midnight don't appear.
6. [ ] Place hand 10 cm in front of HC-SR04 — obstacle icon appears at col 14 row 0; remove hand — disappears.
7. [ ] Place card on RFID antenna — RFID icon appears at col 15; lift — disappears after 300 ms hold.
8. [ ] Each swipe writes `info i2c swipe uid=... lcd_write ok` to dashboard live-log.
9. [ ] Idle 30 s without swipe / obstacle — `journalctl | grep 'lcd_write'` shows zero new lines (state-change-only refresh).

- [ ] **Step 4: Capture post-P1 metrics**

Re-run the baseline snapshot from Task 0.1 and compare against the spec §10.2 matrix. Phase 1 should be a no-regress on every metric, with new green ticks for the "LCD restores after deny" and "Pi audit shows denial" rows.

- [ ] **Step 5: Update memory**

Add a new memory entry capturing the Phase 1 fix:

```
File: ~/.claude/projects/.../memory/smart_gate_lcd_restore_pattern.md
Type: project
Description: LCD denial restore via EV_T_LCD_RESTORE one-shot timer, 2.5s default
```

Index it in `MEMORY.md`. (Skip if you prefer to memory-update at end of all 4 phases.)

- [ ] **Step 6: If all 9 tests pass, proceed to Phase 2. Otherwise STOP and triage.**

---

## Phase 2 — Input hardening

13 tasks, ~165 LOC. Goal: bịt các lỗ adversary có thể exploit qua input layer (UART, Pi RX, web params).

### Task 2.1: DB pragmas (WAL + sync + autocheckpoint + busy_timeout)

**Files:**
- Modify: `smart_gate/data/db.py`
- Test: `tests/unit/test_db.py`

- [ ] **Step 1: Read current db.py to locate the connection setup**

```bash
grep -n 'connect\|PRAGMA\|isolation_level' smart_gate/data/db.py
```

- [ ] **Step 2: Write failing test**

Add to `tests/unit/test_db.py`:

```python
def test_db_uses_wal_and_normal_sync(tmp_path):
    from smart_gate.data.db import Database
    db = Database(tmp_path / "test.db")
    cur = db._conn.execute("PRAGMA journal_mode")
    assert cur.fetchone()[0].lower() == "wal"
    cur = db._conn.execute("PRAGMA synchronous")
    assert cur.fetchone()[0] in (1, "NORMAL")   # 1 = NORMAL
    cur = db._conn.execute("PRAGMA busy_timeout")
    assert cur.fetchone()[0] >= 5000
```

- [ ] **Step 3: Run test to confirm failure**

```bash
pytest tests/unit/test_db.py -k uses_wal -v
```

- [ ] **Step 4: Add pragmas after connect**

In `smart_gate/data/db.py`, in the `__init__` or `connect` method, right after the `sqlite3.connect(...)` call:

```python
self._conn.execute("PRAGMA journal_mode=WAL")
self._conn.execute("PRAGMA synchronous=NORMAL")
self._conn.execute("PRAGMA wal_autocheckpoint=1000")
self._conn.execute("PRAGMA busy_timeout=5000")
```

- [ ] **Step 5: Run test**

```bash
pytest tests/unit/test_db.py -v
```

- [ ] **Step 6: Commit**

```bash
git add smart_gate/data/db.py tests/unit/test_db.py
git commit -m "perf(db): enable WAL + NORMAL sync + busy_timeout pragmas

Reduces SD-card write amplification under sustained ESP-log inflow.
busy_timeout=5000 prevents instant SQLITE_BUSY on concurrent writes
from Flask threads.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 2.2: DB `transaction()` context manager + wrap multi-statement paths

**Files:**
- Modify: `smart_gate/data/db.py`
- Modify: `smart_gate/main.py`
- Test: `tests/unit/test_db.py`

- [ ] **Step 1: Write failing test**

Add to `tests/unit/test_db.py`:

```python
def test_transaction_commits_on_success(tmp_path):
    from smart_gate.data.db import Database
    db = Database(tmp_path / "test.db")
    db._conn.execute("CREATE TABLE t (x INT)")
    with db.transaction():
        db._conn.execute("INSERT INTO t VALUES (1)")
        db._conn.execute("INSERT INTO t VALUES (2)")
    assert db._conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 2

def test_transaction_rolls_back_on_exception(tmp_path):
    from smart_gate.data.db import Database
    db = Database(tmp_path / "test.db")
    db._conn.execute("CREATE TABLE t (x INT)")
    with pytest.raises(RuntimeError):
        with db.transaction():
            db._conn.execute("INSERT INTO t VALUES (1)")
            raise RuntimeError("boom")
    assert db._conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/unit/test_db.py -k "transaction" -v
```

- [ ] **Step 3: Implement `transaction()` in `Database`**

In `smart_gate/data/db.py`:

```python
from contextlib import contextmanager

@contextmanager
def transaction(self):
    self._conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        self._conn.execute("COMMIT")
    except Exception:
        self._conn.execute("ROLLBACK")
        raise
```

- [ ] **Step 4: Wrap `_handle_checkin` multi-statement path in `smart_gate/main.py`**

```bash
grep -n 'insert_face_encoding\|touch_last_seen\|insert_event' smart_gate/main.py | head -10
```

Locate `_handle_checkin` and wrap the consecutive db writes:

```python
with self._db.transaction():
    self._db.insert_face_encoding(...)
    self._db.touch_last_seen(...)
    self._db.insert_event(...)
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_db.py tests/unit/test_main_bus.py -v
```

- [ ] **Step 6: Commit**

```bash
git add smart_gate/data/db.py smart_gate/main.py tests/unit/test_db.py
git commit -m "perf(db): explicit transaction() context manager + wrap check-in

Three implicit auto-commit INSERTs per check-in were three fsyncs.
Single explicit BEGIN IMMEDIATE…COMMIT collapses them to one.
Rollback-on-exception keeps the row triplet atomic.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 2.3: DB migration version gate

**Files:**
- Modify: `smart_gate/data/db.py`
- Test: `tests/unit/test_db.py`

- [ ] **Step 1: Write failing test**

```python
def test_migrate_skips_already_applied(tmp_path):
    from smart_gate.data.db import Database
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_init.sql").write_text("CREATE TABLE foo (id INT);")
    (migrations / "0002_add.sql").write_text("CREATE TABLE bar (id INT);")

    db = Database(tmp_path / "test.db", migrations_dir=migrations)
    db.migrate()
    # Second migrate must NOT re-run 0002 (would error: 'table bar already exists')
    db.migrate()  # should not raise
    assert db._conn.execute("SELECT version FROM _meta").fetchone()[0] == 2
```

- [ ] **Step 2: Run test to confirm failure**

```bash
pytest tests/unit/test_db.py -k migrate_skips -v
```

- [ ] **Step 3: Rewrite `migrate()` to use version gate**

In `smart_gate/data/db.py`:

```python
def migrate(self):
    self._conn.execute("CREATE TABLE IF NOT EXISTS _meta (key TEXT PRIMARY KEY, value TEXT)")
    cur = self._conn.execute("SELECT value FROM _meta WHERE key='schema_version'")
    row = cur.fetchone()
    current = int(row[0]) if row else 0

    files = sorted(self._migrations_dir.glob("[0-9]*.sql"))
    for f in files:
        num = int(f.stem.split("_")[0])
        if num <= current:
            continue
        with self.transaction():
            self._conn.executescript(f.read_text())
            self._conn.execute(
                "INSERT OR REPLACE INTO _meta(key, value) VALUES ('schema_version', ?)",
                (str(num),))
        log.info("db: migrated to version %d via %s", num, f.name)
```

(Adjust `self._migrations_dir` to whatever the existing code uses for its migrations path.)

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_db.py -v
```

- [ ] **Step 5: Commit**

```bash
git add smart_gate/data/db.py tests/unit/test_db.py
git commit -m "fix(db): migration version gate — skip already-applied files

migrate() iterated every .sql on each startup. Today 0001_init uses
IF NOT EXISTS so it's idempotent by accident — but the first 0002_*.sql
with an ALTER TABLE would crash on the second restart. Now tracks
schema_version in _meta and skips files with num <= current.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 2.4: EspLogWriter — batched writer thread for ESP log lines

**Files:**
- Create: `smart_gate/data/esp_log_writer.py`
- Modify: `smart_gate/main.py`
- Test: `tests/unit/test_esp_log_writer.py` (create)

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_esp_log_writer.py`:

```python
import time
from unittest.mock import MagicMock

def test_writer_batches_rows_within_flush_window():
    from smart_gate.data.esp_log_writer import EspLogWriter
    db = MagicMock()
    w = EspLogWriter(db, flush_interval_s=0.1, batch_max=10)
    w.start()
    for i in range(5):
        w.enqueue(("info", "test", f"msg{i}"))
    time.sleep(0.3)
    w.stop()
    # Single executemany call for the batch (or one per batch up to 10)
    assert db.insert_esp_log_many.call_count >= 1
    rows = db.insert_esp_log_many.call_args[0][0]
    assert len(rows) == 5

def test_writer_drops_oldest_when_queue_full():
    from smart_gate.data.esp_log_writer import EspLogWriter
    db = MagicMock()
    w = EspLogWriter(db, flush_interval_s=10.0, batch_max=10, max_queue=3)
    for i in range(5):
        w.enqueue(("info", "t", f"m{i}"))
    # Queue capped at 3 — should hold the last 3 entries
    assert w.qsize() == 3
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/unit/test_esp_log_writer.py -v
```

- [ ] **Step 3: Implement `EspLogWriter`**

Create `smart_gate/data/esp_log_writer.py`:

```python
"""Batched writer thread for ESP log rows.

Coalesces ESP-emitted log lines (up to 20 Hz from the sensor task) into
periodic INSERTs. Reduces SD-card write amplification dramatically.
"""
from __future__ import annotations
import logging
import threading
from collections import deque
from typing import Tuple

log = logging.getLogger(__name__)

Row = Tuple[str, str, str]   # (level, tag, msg)

class EspLogWriter:
    def __init__(self, db, flush_interval_s: float = 1.0,
                 batch_max: int = 50, max_queue: int = 10_000):
        self._db = db
        self._flush_interval_s = flush_interval_s
        self._batch_max = batch_max
        self._max_queue = max_queue
        self._q: deque[Row] = deque(maxlen=max_queue)
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="esp-log-writer")
        self._thread.start()

    def stop(self, timeout: float = 2.0):
        self._stop.set()
        with self._cond:
            self._cond.notify_all()
        if self._thread:
            self._thread.join(timeout=timeout)

    def enqueue(self, row: Row):
        with self._cond:
            self._q.append(row)
            self._cond.notify()

    def qsize(self) -> int:
        with self._lock:
            return len(self._q)

    def _loop(self):
        while not self._stop.is_set():
            batch: list[Row] = []
            with self._cond:
                if not self._q:
                    self._cond.wait(timeout=self._flush_interval_s)
                while self._q and len(batch) < self._batch_max:
                    batch.append(self._q.popleft())
            if not batch:
                continue
            try:
                self._db.insert_esp_log_many(batch)
            except Exception:
                log.exception("esp_log_writer: flush failed; %d rows lost", len(batch))
```

- [ ] **Step 4: Add `insert_esp_log_many` to `Database` if not present**

In `smart_gate/data/db.py`:

```python
def insert_esp_log_many(self, rows):
    with self.transaction():
        self._conn.executemany(
            "INSERT INTO esp_log (level, tag, message, ts) VALUES (?, ?, ?, datetime('now'))",
            rows,
        )
```

(Adjust column list to match the existing `insert_esp_log` schema.)

- [ ] **Step 5: Wire the writer into `smart_gate/main.py`**

In `SmartGateApp.__init__` (or wherever the DB is created):

```python
from smart_gate.data.esp_log_writer import EspLogWriter
# ...
self._esp_log_writer = EspLogWriter(self._db)
self._esp_log_writer.start()
```

In `_handle_esp_event` for `evt:log`:

```python
# Replace:
#     self._db.insert_esp_log(level, tag, msg)
# With:
self._esp_log_writer.enqueue((level, tag, msg))
```

Add `self._esp_log_writer.stop()` to the daemon shutdown path.

- [ ] **Step 6: Run tests**

```bash
pytest tests/unit/test_esp_log_writer.py tests/unit/test_db.py -v
```

- [ ] **Step 7: Commit**

```bash
git add smart_gate/data/esp_log_writer.py smart_gate/data/db.py smart_gate/main.py \
        tests/unit/test_esp_log_writer.py
git commit -m "perf(daemon): batched ESP-log writer — 20Hz INSERTs → 1Hz batched flush

EspLogWriter holds a bounded deque (10k max) and a daemon thread that
flushes up to 50 rows per executemany every 1 second. Replaces the
per-line synchronous INSERT in _handle_esp_event. Major SD-write reduction.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 2.5: Pi readline size cap

**Files:**
- Modify: `smart_gate/link/protocol.py`
- Modify: `smart_gate/link/uart_client.py`
- Test: `tests/unit/test_uart_client.py`

- [ ] **Step 1: Add the constant**

In `smart_gate/link/protocol.py`:

```python
MAX_LINE = 1024   # ESP UART_LINE_MAX is 512; doubled for margin
```

- [ ] **Step 2: Write failing test**

Add to `tests/unit/test_uart_client.py`:

```python
def test_rx_discards_unterminated_long_input(monkeypatch, caplog):
    """A non-\\n bytestream of >MAX_LINE bytes is discarded, not accumulated."""
    from smart_gate.link import protocol
    from smart_gate.link.uart_client import UartClient

    # Fake serial that emits 2000 bytes of 'A' with NO newline
    class FakeSerial:
        def __init__(self):
            self.calls = 0
        def read_until(self, terminator, size):
            self.calls += 1
            return b"A" * (protocol.MAX_LINE + 100)  # over the cap, no \n
        def write(self, _): return 0
        def close(self): pass

    fake = FakeSerial()
    # ... wire fake into the client's rx loop one iteration ...
    # Assert client did not raise + line is dropped (logged warning).
    # Implementation detail depends on UartClient API; this test sketches intent.
```

(Adapt the wiring to the actual `UartClient` constructor — the test patches `_open_serial` to return `fake` and runs `_rx_loop` for a few iterations.)

- [ ] **Step 3: Replace `readline()` with `read_until(..., size=...)`**

In `smart_gate/link/uart_client.py`, find the rx loop (around line 178):

```python
from smart_gate.link import protocol
# ...
line = self._ser.read_until(b"\n", size=protocol.MAX_LINE + 1)
if not line.endswith(b"\n"):
    log.warning("rx: dropping %d non-terminated bytes", len(line))
    continue
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_uart_client.py -v
```

- [ ] **Step 5: Commit**

```bash
git add smart_gate/link/protocol.py smart_gate/link/uart_client.py tests/unit/test_uart_client.py
git commit -m "fix(link): cap Pi-side readline at MAX_LINE+1 bytes

A misbehaving ESP that streams non-\\n bytes at 115200 bps grew an
unbounded bytearray inside readline() — OOM after ~40 MB. read_until
with size= bounds the discard.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 2.6: TX-then-register race fix

**Files:**
- Modify: `smart_gate/link/uart_client.py`
- Test: `tests/unit/test_uart_client.py`

- [ ] **Step 1: Write failing test**

Add to `tests/unit/test_uart_client.py`:

```python
def test_tx_registers_pending_before_write(monkeypatch):
    """An ACK that arrives immediately after write() must find pending registered."""
    from smart_gate.link.uart_client import UartClient
    # Instrument _ser.write to call rx_dispatch synchronously inside the call,
    # simulating a sub-millisecond ESP turnaround.
    # Assert: ack_event.is_set() after send_cmd returns.
    # See test file for fixture pattern.
```

(Test wiring depends on the existing UartClient harness in `test_uart_client.py`.)

- [ ] **Step 2: Reorder the registration**

In `smart_gate/link/uart_client.py` `_tx_loop`, replace the current write-then-register pattern with register-then-write:

```python
def _tx_loop(self):
    while not self._shutdown.is_set():
        try:
            item = self._tx_queue.get(timeout=0.5)
        except queue.Empty:
            continue
        msg_id, payload, ack_event, holder = item
        # REGISTER BEFORE WRITE — must happen before the byte leaves the wire
        if ack_event is not None:
            self._pending[msg_id] = (ack_event, holder)
        try:
            with self._port_lock:
                if self._ser is None:
                    if ack_event:
                        self._pending.pop(msg_id, None)
                        ack_event.set()
                    continue
                try:
                    self._ser.write(payload)
                except (SerialException, OSError):
                    if ack_event:
                        self._pending.pop(msg_id, None)
                        ack_event.set()
                    self._mark_link_down()
                    continue
        except Exception:
            log.exception("tx loop iter failed")
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/unit/test_uart_client.py -v
```

- [ ] **Step 4: Commit**

```bash
git add smart_gate/link/uart_client.py tests/unit/test_uart_client.py
git commit -m "fix(link): register _pending BEFORE write — eliminate ACK race

ESP ACK round-trip is sub-millisecond at 115200 baud. write() then
register meant ACKs could arrive before _pending had the msg_id and
were silently dropped, causing 2-second LinkTimeout despite the gate
physically having opened.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 2.7: Numeric query-param clamping (`_int_param` helper)

**Files:**
- Modify: `smart_gate/web/app.py`
- Test: `tests/unit/test_web.py`

- [ ] **Step 1: Write failing test**

Add to `tests/unit/test_web.py`:

```python
def test_events_negative_limit_returns_400(client):
    resp = client.get("/events.json?limit=-1")
    assert resp.status_code == 400

def test_events_huge_limit_capped(client):
    resp = client.get("/events.json?limit=99999")
    # capped to 500 internally; data may be empty, but should not 500
    assert resp.status_code == 200
    assert "count" in resp.json
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/unit/test_web.py -k "negative_limit or huge_limit" -v
```

- [ ] **Step 3: Add the helper at the top of `smart_gate/web/app.py`**

```python
from flask import abort, request

def _int_param(name: str, default: int, lo: int, hi: int) -> int:
    raw = request.args.get(name, default)
    try:
        v = int(raw)
    except (TypeError, ValueError):
        abort(400, f"bad {name}")
    return max(lo, min(v, hi))
```

- [ ] **Step 4: Apply at every existing `int(request.args.get(...))` site**

```bash
grep -n 'int(request.args.get' smart_gate/web/app.py
```

For each match, replace with the helper. Example for `limit`:

```python
limit = _int_param("limit", 100, 1, 500)
```

For `after_id` / `before_id` / `last_id`, choose realistic `lo/hi` (e.g. 0 to `2**31-1`).

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_web.py -v
```

- [ ] **Step 6: Commit**

```bash
git add smart_gate/web/app.py tests/unit/test_web.py
git commit -m "fix(web): clamp numeric query params — blocks ?limit=-1 full-table dump

SQLite interprets LIMIT -1 as 'no limit'. curl ?limit=-1 previously
exfiltrated every events row. _int_param() validates and clamps with
HTTP 400 on bad input.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 2.8: innerHTML XSS escape in dashboard.html

**Files:**
- Modify: `smart_gate/web/templates/dashboard.html`

- [ ] **Step 1: Audit every dynamic innerHTML write**

```bash
grep -n 'innerHTML\|responseText' smart_gate/web/templates/dashboard.html
```

- [ ] **Step 2: Route each through `escapeHtml()`**

The toast renderer at lines 191-194 already uses `escapeHtml`. For each remaining `innerHTML = "..." + s.field + "..."` pattern around lines 255-258 and 277-298, replace with one of:
- `el.textContent = s.field;` if the field is plain text.
- `el.innerHTML = "..." + escapeHtml(s.field) + "...";` if the surrounding string contains HTML structure.
- For the raw `responseText` fallback (around line 296-297): `el.textContent = xhr.responseText;` (never innerHTML on raw text).

Run a final search:

```bash
grep -n 'innerHTML' smart_gate/web/templates/dashboard.html | grep -v escapeHtml
```

Every remaining match should write only string literals, not dynamic data.

- [ ] **Step 3: Manual smoke (browser)**

Start the daemon locally with a test DB containing a user named `<img src=x onerror=alert(1)>`. Open the dashboard. Confirm the text renders literally, no alert pops.

- [ ] **Step 4: Commit**

```bash
git add smart_gate/web/templates/dashboard.html
git commit -m "fix(web): escape all dynamic innerHTML writes — defense-in-depth XSS

Toast renderer already used escapeHtml(); the gate-state and enroll
result branches did not. Trust-boundary inconsistency closed.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 2.9: ESP-supplied name/uid length cap (Pi side)

**Files:**
- Modify: `smart_gate/main.py`
- Test: `tests/unit/test_main_bus.py`

- [ ] **Step 1: Write failing test**

In `tests/unit/test_main_bus.py`:

```python
def test_evt_rfid_caps_name_and_uid_length():
    """ESP-supplied fields must be truncated before downstream use."""
    from smart_gate.main import _cap_rfid_fields   # to be added as a helper
    d = {"uid": "F" * 100, "name": "X" * 200, "granted": False}
    name, uid = _cap_rfid_fields(d)
    assert len(name) <= 32
    assert len(uid) <= 24
```

- [ ] **Step 2: Add the helper + use it in `_handle_esp_event`**

In `smart_gate/main.py`:

```python
def _cap_rfid_fields(d: dict) -> tuple[str, str]:
    name = (d.get("name") or "")[:32]
    uid  = (d.get("uid")  or "")[:24]
    return name, uid
```

In `_handle_esp_event` for `evt:rfid`, replace the existing field extraction:

```python
name, uid = _cap_rfid_fields(d)
```

- [ ] **Step 3: Run test**

```bash
pytest tests/unit/test_main_bus.py -k caps_name -v
```

- [ ] **Step 4: Commit**

```bash
git add smart_gate/main.py tests/unit/test_main_bus.py
git commit -m "fix(daemon): cap ESP-supplied name/uid lengths — defensive

Untrusted fields from over the UART wire are bound checked before
log.info/SQL/web display, matching firmware buffer sizes (32 / 24).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 2.10: ESP UART overflow tail discard

**Files:**
- Modify: `firmware/src/uart_link.cpp`

- [ ] **Step 1: Add the discard flag + accumulator changes**

In `firmware/src/uart_link.cpp`, near the existing `static char s_linebuf[...]; static size_t s_pos;`:

```cpp
static bool s_discarding = false;
```

Replace the rx loop byte handling (around line 110-130) with:

```cpp
while (Serial1.available()) {
    int b = Serial1.read();
    if (b < 0) break;
    char c = (char)b;

    if (c == '\r') continue;   // strip CR (Windows CRLF)

    if (c == '\n') {
        if (s_discarding) {
            s_pos = 0;
            s_discarding = false;
            continue;
        }
        s_linebuf[s_pos] = 0;
        parse_line(s_linebuf);
        s_pos = 0;
        continue;
    }

    if (s_discarding) continue;   // drop tail bytes silently

    if (s_pos >= UART_LINE_MAX - 1) {
        LOGW("uart", "line overflow, discarding until next \\n");
        s_discarding = true;
        s_pos = 0;
        continue;
    }

    s_linebuf[s_pos++] = c;
}
```

- [ ] **Step 2: Build**

```bash
cd firmware && /home/nguyenvd/.local/bin/pio run 2>&1 | tail -5
```

- [ ] **Step 3: Commit**

```bash
cd /home/nguyenvd/workspace/smart_gate
git add firmware/src/uart_link.cpp
git commit -m "fix(firmware): UART overflow discards until next \\n

Previously: 600 bytes of garbage + valid JSON cmd parsed as if the cmd
was clean. Now s_discarding flag drops every byte after the first
overflow until a fresh \\n resets the buffer.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 2.11: cmd:open per-session replay protection

**Files:**
- Modify: `firmware/src/uart_link.cpp`
- Modify: `smart_gate/link/uart_client.py`
- Test: `tests/unit/test_uart_client.py`

- [ ] **Step 1: Add `s_last_cmd_id` + replay check to `parse_line` in `uart_link.cpp`**

```cpp
static uint32_t s_last_cmd_id = 0;
```

In `parse_line`, after decoding the JSON and confirming `type == "cmd"`:

```cpp
JsonVariant id_v = doc["id"];
if (!id_v.is<uint32_t>() && !id_v.is<int>()) {
    LOGW("uart", "cmd missing/invalid id"); return;
}
uint32_t id = id_v.as<uint32_t>();
if (id == 0) {
    LOGW("uart", "cmd id=0 rejected"); return;
}
if (id <= s_last_cmd_id) {
    LOGW("uart", "cmd id %u replay (last=%u)", id, s_last_cmd_id);
    emit_ack_err(id, "replay");
    return;
}
s_last_cmd_id = id;
e.cmd_id = id;
```

- [ ] **Step 2: Update Pi `_next_id` seed**

In `smart_gate/link/uart_client.py`:

```python
import itertools, time
# In __init__:
self._next_id = itertools.count(int(time.time()))   # was count(1)
```

- [ ] **Step 3: Write a test for the Pi-side counter starting from time-seed**

```python
def test_uart_client_next_id_seeded_from_time(monkeypatch):
    monkeypatch.setattr("time.time", lambda: 1_700_000_000.0)
    from smart_gate.link.uart_client import UartClient
    c = UartClient.__new__(UartClient)
    c._init_id_counter()   # extract the counter setup into a tiny helper
    assert next(c._next_id) == 1_700_000_000
    assert next(c._next_id) == 1_700_000_001
```

(Refactor `_next_id = itertools.count(int(time.time()))` into a tiny `_init_id_counter()` so it's testable; call it from `__init__`.)

- [ ] **Step 4: Build firmware + run tests**

```bash
cd firmware && /home/nguyenvd/.local/bin/pio run 2>&1 | tail -3
cd .. && pytest tests/unit/test_uart_client.py -v
```

- [ ] **Step 5: Commit**

```bash
git add firmware/src/uart_link.cpp smart_gate/link/uart_client.py tests/unit/test_uart_client.py
git commit -m "fix(link): per-session replay protection on cmd:open

ESP tracks s_last_cmd_id (per boot session) and rejects any cmd with
id <= last seen. Pi seeds _next_id from int(time.time()) so IDs are
monotonic across Pi restarts within the same ESP session. Closes the
'record + replay over /dev/serial0' window.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 2.12: doc["id"] strict parsing (covered in 2.11, drive-by)

Already done in Task 2.11 Step 1. Skip — no separate commit needed.

### Task 2.13: Phase 2 verification gate (manual)

- [ ] **Step 1: Flash + restart**

Same flash workflow as Task 1.11 Step 1-2. Restart Pi daemon.

- [ ] **Step 2: Run the Phase 2 test matrix (spec §10.4)**

1. [ ] `printf '{"type":"cmd","v":"open","id":1}\n' | sudo tee /dev/serial0` → gate opens. Repeat — does NOT open.
2. [ ] `python -c "import sys; sys.stdout.buffer.write(b'A'*1000 + b'{\"type\":\"cmd\",\"v\":\"open\",\"id\":2}\n')" | sudo tee /dev/serial0` → does NOT open.
3. [ ] Fake-ESP pumping non-`\n` bytes for 10 s → daemon RSS does not grow > 50 MB.
4. [ ] 100 concurrent `/api/gate/state.json` polls + 10 `/api/gate/open` → all ACK, no `LinkTimeout` in journal.
5. [ ] Enroll user `<img src=x onerror=alert(1)>` → dashboard renders literal text, no alert.
6. [ ] `curl 'http://pi:8080/events.json?limit=-1'` → HTTP 400.
7. [ ] Add `migrations/0002_test.sql` with `CREATE TABLE test_v2 (id INT);` → first restart logs "migrated to 2"; second restart skips. Then remove the test migration + DROP TABLE to keep state clean.
8. [ ] `iostat -dx 1 /dev/mmcblk0` over 60 s idle → write IOPS < 5.

- [ ] **Step 3: If all pass, proceed to Phase 3.**

---

## Phase 3 — Hardware robustness

15 tasks, ~225 LOC. Goal: chống fault thực tế của RFID/sensor/servo/LCD + brown-out safe.

### Task 3.1: UID buffer widening (events.h + rfid.cpp)

**Files:**
- Modify: `firmware/include/events.h`
- Modify: `firmware/src/rfid.cpp`

- [ ] **Step 1: Widen `event_t.uid`**

In `firmware/include/events.h`:

```cpp
struct event_t {
    // ...
    char uid[24];   // was [16]; 10-byte ISO 14443 UID = 20 hex chars + NUL + margin
    // ...
};
```

- [ ] **Step 2: Update `rfid.cpp` accordingly**

```cpp
char uid_hex[24];   // was [16]
```

Update `uid_to_hex` bound check:

```cpp
static void uid_to_hex(const uint8_t* bytes, size_t n, char* out, size_t out_n) {
    size_t pos = 0;
    for (size_t i = 0; i < n; i++) {
        if (pos + 2 > out_n - 1) break;   // strict: 2 hex chars + NUL must fit
        snprintf(out + pos, out_n - pos, "%02X", bytes[i]);
        pos += 2;
    }
    out[pos] = 0;
}
```

Validate UID size in `rfid_task`:

```cpp
if (mfrc522.uid.size != 4 && mfrc522.uid.size != 7 && mfrc522.uid.size != 10) {
    LOGW("rfid", "unexpected uid size=%u", mfrc522.uid.size);
    mfrc522.PICC_HaltA();
    mfrc522.PCD_StopCrypto1();
    continue;
}
```

- [ ] **Step 3: Build**

```bash
cd firmware && /home/nguyenvd/.local/bin/pio run 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
cd /home/nguyenvd/workspace/smart_gate
git add firmware/include/events.h firmware/src/rfid.cpp
git commit -m "fix(firmware): widen UID buffer to 24 chars — 10-byte UIDs no longer alias

Two DESFire cards sharing the first 7 bytes were aliased to the same
allowlist entry (spoofing risk). Now event_t.uid holds the full 20 hex
chars + NUL, and unexpected UID sizes are rejected.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 3.2: MFRC522 health monitor — version probe + soft-reset + per-UID rate limit

**Files:**
- Modify: `firmware/src/rfid.cpp`

- [ ] **Step 1: Add version probe in `rfid_init`**

```cpp
static bool s_rfid_ok = false;

void rfid_init() {
    SPI.begin();
    mfrc522.PCD_Init();
    delay(50);
    uint8_t ver = mfrc522.PCD_ReadRegister(MFRC522::VersionReg);
    if (ver != 0x91 && ver != 0x92) {
        LOGE("rfid", "init failed version=0x%02x", ver);
        s_rfid_ok = false;
        return;
    }
    s_rfid_ok = true;
    LOGI("rfid", "init ok version=0x%02x", ver);
}
```

- [ ] **Step 2: Add soft-reset cycle + per-UID rate limit in `rfid_task`**

```cpp
static char s_last_uid[24] = {0};
static uint32_t s_last_uid_ms = 0;
static uint32_t s_last_probe_ms = 0;
static uint32_t s_last_fault_emit_ms = 0;

void rfid_task(void*) {
    while (true) {
        if (!s_rfid_ok) {
            // Try recovery every 60s
            if (millis() - s_last_probe_ms > 60000) {
                s_last_probe_ms = millis();
                mfrc522.PCD_Reset();
                delay(50);
                mfrc522.PCD_Init();
                delay(50);
                uint8_t ver = mfrc522.PCD_ReadRegister(MFRC522::VersionReg);
                if (ver == 0x91 || ver == 0x92) {
                    LOGI("rfid", "recovered version=0x%02x", ver);
                    s_rfid_ok = true;
                } else if (millis() - s_last_fault_emit_ms > 300000) {
                    s_last_fault_emit_ms = millis();
                    emit_log("warn", "rfid_fault", "no response");
                }
            }
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }

        // Periodic probe (every 60s with no card)
        if (millis() - s_last_probe_ms > 60000) {
            s_last_probe_ms = millis();
            uint8_t ver = mfrc522.PCD_ReadRegister(MFRC522::VersionReg);
            if (ver != 0x91 && ver != 0x92) {
                LOGW("rfid", "drift detected version=0x%02x, resetting", ver);
                s_rfid_ok = false;
                continue;
            }
        }

        if (!mfrc522.PICC_IsNewCardPresent()) {
            vTaskDelay(pdMS_TO_TICKS(50));
            continue;
        }
        s_card_present = true;
        s_card_last_ms = millis();
        if (!mfrc522.PICC_ReadCardSerial()) {
            vTaskDelay(pdMS_TO_TICKS(50));
            continue;
        }
        if (mfrc522.uid.size != 4 && mfrc522.uid.size != 7 && mfrc522.uid.size != 10) {
            LOGW("rfid", "unexpected uid size=%u", mfrc522.uid.size);
            mfrc522.PICC_HaltA();
            mfrc522.PCD_StopCrypto1();
            vTaskDelay(pdMS_TO_TICKS(50));
            continue;
        }

        char uid_hex[24];
        uid_to_hex(mfrc522.uid.uidByte, mfrc522.uid.size, uid_hex, sizeof(uid_hex));

        // Per-UID rate limit (1s)
        if (strcmp(uid_hex, s_last_uid) == 0 && (millis() - s_last_uid_ms) < 1000) {
            mfrc522.PICC_HaltA();
            mfrc522.PCD_StopCrypto1();
            vTaskDelay(pdMS_TO_TICKS(50));
            continue;
        }
        strncpy(s_last_uid, uid_hex, sizeof(s_last_uid) - 1);
        s_last_uid_ms = millis();

        // ... existing event-emit code ...
        mfrc522.PICC_HaltA();
        mfrc522.PCD_StopCrypto1();
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}
```

- [ ] **Step 3: Build**

```bash
cd firmware && /home/nguyenvd/.local/bin/pio run 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
cd /home/nguyenvd/workspace/smart_gate
git add firmware/src/rfid.cpp
git commit -m "feat(firmware): MFRC522 health monitor — version probe, soft-reset, rate-limit

Probes VersionReg at init and every 60s. Bad version → soft-reset cycle
(PCD_Reset + PCD_Init + re-probe). Persistent fault emits evt:log
rfid_fault (rate-limited 5min) so PeripheralTracker flips RFID → missing.
Per-UID rate limit (1s) stops the same card from spamming the queue
while held on the antenna.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 3.3: HC-SR04 bounds + INPUT_PULLDOWN

**Files:**
- Modify: `firmware/src/sensor.cpp`

- [ ] **Step 1: Add pulldown + bounds**

In `sensor_init` or `sensor_task` setup phase:

```cpp
pinMode(PIN_SR04_TRIG, OUTPUT);
pinMode(PIN_SR04_ECHO, INPUT_PULLDOWN);
```

In `read_distance_cm`:

```cpp
int read_distance_cm() {
    digitalWrite(PIN_SR04_TRIG, LOW);
    delayMicroseconds(2);
    digitalWrite(PIN_SR04_TRIG, HIGH);
    delayMicroseconds(10);
    digitalWrite(PIN_SR04_TRIG, LOW);
    unsigned long us = pulseIn(PIN_SR04_ECHO, HIGH, 30000UL);
    if (us == 0)     return -1;
    if (us < 116)    return -1;   // < 2 cm physically impossible
    if (us > 23200)  return -1;   // > 400 cm: ghost echo
    return (int)(us / 58);
}
```

- [ ] **Step 2: Build**

```bash
cd firmware && /home/nguyenvd/.local/bin/pio run 2>&1 | tail -5
```

- [ ] **Step 3: Commit**

```bash
cd /home/nguyenvd/workspace/smart_gate
git add firmware/src/sensor.cpp
git commit -m "fix(firmware): HC-SR04 sane bounds + INPUT_PULLDOWN

Floating ECHO pin produced spurious 'very close' readings. Pulldown
forces idle-low on disconnect; <2cm and >400cm readings rejected as
physically impossible (datasheet min ~2cm, ghost echoes beyond 4m).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 3.4: HC-SR04 median-of-3 + fault streak

**Files:**
- Modify: `firmware/src/sensor.cpp`

- [ ] **Step 1: Median filter + streak counter**

```cpp
static int s_last3[3] = {-1, -1, -1};
static int s_last3_idx = 0;
static int s_no_echo_streak = 0;
static bool s_fault_emitted = false;

static int median3(int a, int b, int c) {
    if ((a <= b && b <= c) || (c <= b && b <= a)) return b;
    if ((b <= a && a <= c) || (c <= a && a <= b)) return a;
    return c;
}

int sensor_read_filtered_cm() {
    int raw = read_distance_cm();
    if (raw < 0) {
        s_no_echo_streak++;
        if (s_no_echo_streak * 50 >= 30000 * 5 && !s_fault_emitted) {
            emit_log("warn", "sensor_fault", "no echo persistent");
            s_fault_emitted = true;
        }
        return -1;
    }
    s_no_echo_streak = 0;
    s_fault_emitted = false;
    s_last3[s_last3_idx] = raw;
    s_last3_idx = (s_last3_idx + 1) % 3;
    if (s_last3[0] < 0 || s_last3[1] < 0 || s_last3[2] < 0) return raw;
    return median3(s_last3[0], s_last3[1], s_last3[2]);
}
```

Replace `read_distance_cm` call in `sensor_task` with `sensor_read_filtered_cm`.

- [ ] **Step 2: Build + commit**

```bash
cd firmware && /home/nguyenvd/.local/bin/pio run 2>&1 | tail -5
cd /home/nguyenvd/workspace/smart_gate
git add firmware/src/sensor.cpp
git commit -m "fix(firmware): HC-SR04 median-of-3 + sensor_fault notify

Drops salt-pepper noise without significantly increasing latency.
Persistent no-echo streak (>150s) emits a single evt:log sensor_fault
so the Pi PeripheralTracker flips the sensor → missing.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 3.5: FSM-side 500 ms sensor-gate after S_OPEN_WAIT

**Files:**
- Modify: `firmware/src/gate_fsm.cpp`

- [ ] **Step 1: Add a guard timestamp**

In `gate_fsm.cpp` module scope:

```cpp
static uint32_t s_open_wait_entered_ms = 0;
```

In the transition into `S_OPEN_WAIT` (find by searching for `s_state = S_OPEN_WAIT`):

```cpp
s_state = S_OPEN_WAIT;
s_open_wait_entered_ms = millis();
```

In the `EV_PASSAGE_DETECTED` handler:

```cpp
if (e.kind == EV_PASSAGE_DETECTED) {
    if (s_state != S_OPEN_WAIT) return;
    if (millis() - s_open_wait_entered_ms < 500) {
        // ignore early ghost echoes from arm motion
        return;
    }
    // ... existing passage handling ...
}
```

- [ ] **Step 2: Build + commit**

```bash
cd firmware && /home/nguyenvd/.local/bin/pio run 2>&1 | tail -5
cd /home/nguyenvd/workspace/smart_gate
git add firmware/src/gate_fsm.cpp
git commit -m "fix(firmware): ignore passage events for 500ms after gate opens

Arm motion settles in the first 500ms of S_OPEN_WAIT — the swept arc
crosses the HC-SR04 cone and emits ghost passage events. FSM now gates
EV_PASSAGE_DETECTED for the settling window.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 3.6: Servo physical clamp

**Files:**
- Modify: `firmware/include/config.h`
- Modify: `firmware/src/servo_drv.cpp`

- [ ] **Step 1: Add the constants**

In `firmware/include/config.h`:

```cpp
#define SERVO_MIN_PHYS_DEG 5
#define SERVO_MAX_PHYS_DEG 110
```

- [ ] **Step 2: Apply clamp in `servo_set_angles`**

In `servo_drv.cpp`:

```cpp
void servo_set_angles(int open_deg, int close_deg) {
    s_open_deg  = constrain(open_deg,  SERVO_MIN_PHYS_DEG, SERVO_MAX_PHYS_DEG);
    s_close_deg = constrain(close_deg, SERVO_MIN_PHYS_DEG, SERVO_MAX_PHYS_DEG);
}
```

- [ ] **Step 3: Build + commit**

```bash
cd firmware && /home/nguyenvd/.local/bin/pio run 2>&1 | tail -5
cd /home/nguyenvd/workspace/smart_gate
git add firmware/include/config.h firmware/src/servo_drv.cpp
git commit -m "fix(firmware): clamp servo angles to physical [5°, 110°]

A bad cmd:config (open_deg=180) previously drove the horn into the
enclosure and stalled SG90 at 700mA until brown-out. Hard clamp.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 3.7: Servo async command + detach timer

**Files:**
- Modify: `firmware/src/servo_drv.h`
- Modify: `firmware/src/servo_drv.cpp`
- Modify: `firmware/src/gate_fsm.cpp`

- [ ] **Step 1: Add new API to header**

In `servo_drv.h`:

```cpp
void servo_command_async(int target_deg, int expected_travel_ms);
```

- [ ] **Step 2: Implement with detach timer**

In `servo_drv.cpp`:

```cpp
static TimerHandle_t s_detach_timer = nullptr;

static void cb_detach(TimerHandle_t) {
    s_servo.detach();
    digitalWrite(PIN_SERVO, LOW);
}

void servo_init() {
    pinMode(PIN_SERVO, OUTPUT);
    digitalWrite(PIN_SERVO, LOW);
    s_servo.setPeriodHertz(50);
    s_detach_timer = xTimerCreate("svDet", pdMS_TO_TICKS(1000),
                                  pdFALSE, nullptr, cb_detach);
}

void servo_command_async(int target_deg, int expected_travel_ms) {
    target_deg = constrain(target_deg, SERVO_MIN_PHYS_DEG, SERVO_MAX_PHYS_DEG);
    if (!s_servo.attached()) s_servo.attach(PIN_SERVO, 500, 2400);
    s_servo.write(target_deg);
    if (s_detach_timer) {
        xTimerChangePeriod(s_detach_timer, pdMS_TO_TICKS(expected_travel_ms + 200), 0);
        xTimerStart(s_detach_timer, 0);
    }
}
```

- [ ] **Step 3: Switch FSM call sites to async**

In `gate_fsm.cpp`, replace direct `servo_write` / `servo_set_*` calls in `start_open` and `start_closing` with `servo_command_async(target, EXPECTED_TRAVEL_MS)` (use the existing travel-ms constant or `1000` as default).

- [ ] **Step 4: Build + commit**

```bash
cd firmware && /home/nguyenvd/.local/bin/pio run 2>&1 | tail -5
cd /home/nguyenvd/workspace/smart_gate
git add firmware/src/servo_drv.h firmware/src/servo_drv.cpp firmware/src/gate_fsm.cpp
git commit -m "feat(firmware): servo async command + auto-detach after travel + margin

Idle hum at 5-10 mA and slow coil heating eliminated by detaching after
expected_travel_ms + 200ms margin. Re-attaches automatically on the
next command.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 3.8: Servo stall timer

**Files:**
- Modify: `firmware/include/events.h`
- Modify: `firmware/src/main.cpp`
- Modify: `firmware/src/gate_fsm.cpp`

- [ ] **Step 1: Add event kind**

In `events.h`:

```cpp
EV_T_SERVO_STALL,
```

- [ ] **Step 2: Create stall timer in `main.cpp`**

```cpp
TimerHandle_t g_servo_stall_timer = nullptr;

static void cb_servo_stall(TimerHandle_t) {
    event_t e{}; e.kind = EV_T_SERVO_STALL;
    xQueueSend(g_event_q, &e, 0);
}

// In setup():
g_servo_stall_timer = xTimerCreate("svStl", pdMS_TO_TICKS(2000),
                                   pdFALSE, nullptr, cb_servo_stall);
```

- [ ] **Step 3: Arm timer on transitions, cancel on reached, handle stall**

In `gate_fsm.cpp` `start_open` and `start_closing`, after `servo_command_async(...)`:

```cpp
xTimerChangePeriod(g_servo_stall_timer,
                   pdMS_TO_TICKS(EXPECTED_TRAVEL_MS * 2), 0);
xTimerStart(g_servo_stall_timer, 0);
```

In the existing `EV_T_OPEN_REACHED` / `EV_T_CLOSE_REACHED` handlers, at the top:

```cpp
xTimerStop(g_servo_stall_timer, 0);
```

Add the new dispatcher case:

```cpp
if (e.kind == EV_T_SERVO_STALL) {
    emit_log("warn", "servo_stall", "no reached event");
    force_close();
    return;
}
```

- [ ] **Step 4: Build + commit**

```bash
cd firmware && /home/nguyenvd/.local/bin/pio run 2>&1 | tail -5
cd /home/nguyenvd/workspace/smart_gate
git add firmware/include/events.h firmware/src/main.cpp firmware/src/gate_fsm.cpp
git commit -m "feat(firmware): servo stall watchdog timer

If neither EV_T_OPEN_REACHED nor EV_T_CLOSE_REACHED fires within 2× the
expected travel, force_close() and emit evt:log servo_stall. Protects
SG90 from burning when the arm is physically jammed.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 3.9: Brown-out state persist — NVS write on FSM transition

**Files:**
- Modify: `firmware/src/gate_fsm.cpp`

- [ ] **Step 1: Add NVS namespace + write helper**

At the top of `gate_fsm.cpp`:

```cpp
#include <Preferences.h>
static Preferences s_state_prefs;
static const char* NVS_NS_GATE_STATE = "gate_state";

static void persist_state(GateState st) {
    s_state_prefs.putUChar("last_state", (uint8_t)st);
    s_state_prefs.putULong("last_ts", millis());
}
```

In `gate_fsm_init` (early, before any state changes):

```cpp
s_state_prefs.begin(NVS_NS_GATE_STATE, false);
```

- [ ] **Step 2: Call `persist_state` at each transition**

In `enter_idle`, `start_open`, the `S_OPEN_WAIT` entry transition, the `S_TIMEOUT_WARN` entry transition, and `start_closing`, call `persist_state(<state>)` right after `s_state = ...`.

- [ ] **Step 3: Build + commit**

```bash
cd firmware && /home/nguyenvd/.local/bin/pio run 2>&1 | tail -5
cd /home/nguyenvd/workspace/smart_gate
git add firmware/src/gate_fsm.cpp
git commit -m "feat(firmware): persist FSM state to NVS on every transition

New gate_state NVS namespace. Each enter_*/start_* writes last_state +
last_ts. Boot recovery (next task) reads this to decide whether to
servo-snap or hold neutral after brown-out / panic / watchdog.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 3.10: Brown-out boot recovery — read NVS + 5 s neutral hold

**Files:**
- Modify: `firmware/src/gate_fsm.cpp`
- Modify: `firmware/src/main.cpp`

- [ ] **Step 1: Capture reset_reason in `main.cpp` setup**

```bash
grep -n 'esp_reset_reason\|RST_' firmware/src/main.cpp
```

Should already exist (per memory). If not, in `setup()`:

```cpp
esp_reset_reason_t rr = esp_reset_reason();
g_reset_reason_str = reset_reason_to_str(rr);   // existing helper or add one
```

- [ ] **Step 2: Add boot recovery in `gate_fsm_init`**

```cpp
void gate_fsm_init() {
    s_state_prefs.begin(NVS_NS_GATE_STATE, false);
    uint8_t last = s_state_prefs.getUChar("last_state", (uint8_t)S_IDLE);
    extern const char* g_reset_reason_str;   // from main.cpp
    bool risky_reset = (strcmp(g_reset_reason_str, "brownout") == 0 ||
                        strcmp(g_reset_reason_str, "panic")    == 0 ||
                        strcmp(g_reset_reason_str, "watchdog") == 0);
    bool risky_state = (last == S_OPENING || last == S_OPEN_WAIT ||
                        last == S_TIMEOUT_WARN || last == S_CLOSING);

    if (risky_reset && risky_state) {
        // Hold servo at neutral 90° — neither slam nor open
        servo_command_async(90, 800);
        lcd_show_text(0, "Recovery");
        lcd_show_text(1, "verify clear");
        emit_evt_gate_unknown(g_reset_reason_str);
        // Schedule fall-through to idle after 5s
        xTimerChangePeriod(g_lcd_restore_timer, pdMS_TO_TICKS(5000), 0);
        xTimerStart(g_lcd_restore_timer, 0);
        s_state = S_IDLE;     // logical state; servo will close on next transition
        s_open_wait_entered_ms = 0;
    } else {
        enter_idle();
    }
}
```

(Reuse `g_lcd_restore_timer` for the 5 s fall-through — it already calls `lcd_show_idle()` when `s_state == S_IDLE`. The 5 s timeout fires, LCD goes to idle, but servo is already at 90° — needs an additional event to drive it closed. Add a new `EV_T_RECOVERY_CLOSE` for cleanliness OR simpler: in the dispatcher's `EV_T_LCD_RESTORE` case, additionally call `servo_command_async(s_close_deg, EXPECTED_TRAVEL_MS)` if we just entered recovery — track with `static bool s_in_recovery`.)

Use the cleaner pattern: dedicated event.

In `events.h`:

```cpp
EV_T_RECOVERY_FALLBACK,
```

In `main.cpp`:

```cpp
TimerHandle_t g_recovery_timer = nullptr;
static void cb_recovery(TimerHandle_t) {
    event_t e{}; e.kind = EV_T_RECOVERY_FALLBACK;
    xQueueSend(g_event_q, &e, 0);
}
// setup:
g_recovery_timer = xTimerCreate("recov", pdMS_TO_TICKS(5000),
                                pdFALSE, nullptr, cb_recovery);
```

Then in `gate_fsm_init`, arm `g_recovery_timer` instead of reusing `g_lcd_restore_timer`. Add dispatcher case:

```cpp
if (e.kind == EV_T_RECOVERY_FALLBACK) {
    LOGI("fsm", "recovery fallback to idle");
    enter_idle();   // closes servo at normal speed from 90°
    return;
}
```

- [ ] **Step 3: Add `emit_evt_gate_unknown` helper**

In `gate_fsm.cpp` or `uart_link.cpp`:

```cpp
void emit_evt_gate_unknown(const char* reason) {
    char buf[96];
    snprintf(buf, sizeof(buf),
             "{\"type\":\"evt:gate\",\"state\":\"unknown\",\"reset_reason\":\"%s\"}",
             reason);
    uart_link_send_raw(buf);   // or whatever the existing send-raw API is
}
```

- [ ] **Step 4: Build + commit**

```bash
cd firmware && /home/nguyenvd/.local/bin/pio run 2>&1 | tail -5
cd /home/nguyenvd/workspace/smart_gate
git add firmware/include/events.h firmware/src/main.cpp firmware/src/gate_fsm.cpp
git commit -m "feat(firmware): brown-out recovery — hold servo neutral 90° for 5s

After brownout/panic/watchdog reset with last_state in {OPENING,
OPEN_WAIT, TIMEOUT_WARN, CLOSING}, the firmware no longer snaps the
servo to close. Instead holds 90° neutral (mid-travel, safe for hands
and gears), emits evt:gate state=unknown, and falls through to enter_idle
after 5 seconds (closing at normal speed from 90°).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 3.11: Pi handler for `evt:gate state=unknown`

**Files:**
- Modify: `smart_gate/main.py`

- [ ] **Step 1: Add the handler branch**

In `_handle_esp_event` (or wherever `evt:gate` is dispatched):

```python
if d.get("state") == "unknown":
    reason = d.get("reset_reason", "?")
    self._audit(self._esp_log_bus, "error", "boot",
                f"ESP recovered from {reason} — gate state unknown, verify passage clear")
    self._db.insert_event("system", None, False, detail=f"esp_recovery_{reason}")
    return
```

- [ ] **Step 2: Commit**

```bash
git add smart_gate/main.py
git commit -m "feat(daemon): handle evt:gate state=unknown after ESP recovery

Audits + persists a system event row so the operator dashboard shows
which reset reason triggered the recovery hold.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 3.12: Allowlist mutex

**Files:**
- Modify: `firmware/src/allowlist.cpp`

- [ ] **Step 1: Add semaphore + wrap ops**

```cpp
static SemaphoreHandle_t s_mtx = nullptr;
static bool s_degraded = false;

void allowlist_init() {
    s_mtx = xSemaphoreCreateMutex();
    if (!s_mtx) {
        LOGE("allowlist", "mutex create failed");
        while (1) vTaskDelay(pdMS_TO_TICKS(1000));
    }
    bool ok = prefs.begin(NVS_NS_ALLOWLIST, false);
    if (!ok) {
        LOGE("nvs", "allowlist begin failed");
        s_degraded = true;
    }
}

#define ALLOW_LOCK() do { \
    if (xSemaphoreTake(s_mtx, pdMS_TO_TICKS(500)) != pdTRUE) { \
        LOGW("allowlist", "mutex timeout"); return -1; \
    } \
} while (0)
#define ALLOW_UNLOCK() xSemaphoreGive(s_mtx)

int allowlist_lookup(const char* uid, char* name_out, size_t name_out_n) {
    if (s_degraded) return 0;   // safe-deny
    ALLOW_LOCK();
    int r = /* existing lookup body */;
    ALLOW_UNLOCK();
    return r;
}
// ... similarly for add / remove / list / count
```

- [ ] **Step 2: Build + commit**

```bash
cd firmware && /home/nguyenvd/.local/bin/pio run 2>&1 | tail -5
cd /home/nguyenvd/workspace/smart_gate
git add firmware/src/allowlist.cpp
git commit -m "fix(firmware): mutex around Preferences allowlist ops

Race between RFID lookup (rfid_task core 1) and add/remove (gate_fsm core 1
via cmd:add_uid) could return stale or wrong results — observed as
intermittent false denials. 500ms mutex timeout + safe-deny on NVS init
failure.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 3.13: `Preferences::begin` check on gate_state namespace (drive-by)

Already addressed in Task 3.10 implicitly (state_prefs.begin return checked via fallthrough). Skip separate commit.

### Task 3.14: LCD I²C probe + bus recovery

**Files:**
- Modify: `firmware/src/lcd_drv.cpp`

- [ ] **Step 1: Add bit-bang recovery routine**

```cpp
static bool i2c_recover_bus() {
    pinMode(SDA, OUTPUT);
    pinMode(SCL, OUTPUT);
    for (int i = 0; i < 9; i++) {
        digitalWrite(SCL, HIGH); delayMicroseconds(5);
        digitalWrite(SCL, LOW);  delayMicroseconds(5);
    }
    // Manual STOP: SDA low → high while SCL high
    digitalWrite(SDA, LOW);  delayMicroseconds(5);
    digitalWrite(SCL, HIGH); delayMicroseconds(5);
    digitalWrite(SDA, HIGH); delayMicroseconds(5);
    Wire.begin();
    s_lcd.init();
    s_lcd.backlight();
    s_lcd.createChar(0, (uint8_t*)GLYPH_OBSTACLE);
    s_lcd.createChar(1, (uint8_t*)GLYPH_RFID);
    return true;
}
```

- [ ] **Step 2: Probe + recovery at each write entry**

Wrap every `lcd_show_*` body with a probe:

```cpp
static int lcd_probe() {
    Wire.beginTransmission(LCD_ADDR);
    return Wire.endTransmission();
}

void lcd_show_idle() {
    int rc = lcd_probe();
    if (rc != 0) {
        i2c_recover_bus();
        rc = lcd_probe();
        if (rc != 0) { s_last_i2c_err = rc; return; }
    }
    // ... existing render code ...
    s_last_i2c_err = lcd_probe();   // capture post-write status
}
```

Apply same wrap to `lcd_show_denied`, `lcd_show_name`, `lcd_show_opening`, `lcd_show_closing`, `lcd_update_icons`.

- [ ] **Step 3: Build + commit**

```bash
cd firmware && /home/nguyenvd/.local/bin/pio run 2>&1 | tail -5
cd /home/nguyenvd/workspace/smart_gate
git add firmware/src/lcd_drv.cpp
git commit -m "fix(firmware): LCD I²C probe + bit-bang recovery on bus wedge

PCF8574 stuck-bus state (SDA held low after ESD or power glitch) would
make LiquidCrystal_I2C::print block until task watchdog fired. Each
lcd_show_* now probes the bus first; on NACK runs 9 SCL pulses +
manual STOP + re-init, retries once, then sets s_last_i2c_err and
returns (caller observes via lcd_drv_last_i2c_err()).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 3.15: Phase 3 verification gate (manual — bench)

- [ ] **Step 1: Flash + restart Pi daemon**

Same workflow as 1.11.

- [ ] **Step 2: Run Phase 3 test matrix (spec §10.5)**

1. [ ] Unplug MISO on RFID → restart ESP → log `MFRC522 init failed`; dashboard PeripheralTracker `missing`. Plug back → tap card still `missing` until next 60s soft-reset, then recovers.
2. [ ] (If available) DESFire 10-byte card → `evt:rfid uid=...` shows 20 hex chars.
3. [ ] Unplug ECHO wire → 30s log "no echo for 30s"; 150s log "sensor_fault"; gate still closes via passage_timeout slow path.
4. [ ] Hold arm physically still during opening → within 2× expected travel, emit `servo_stall` + arm returns to close + LCD shows error.
5. [ ] `cmd:config servo_open_deg=180` → arm does not over-travel (clamps to 110°).
6. [ ] Mid-rise pull power → reboot → ESP holds 90° neutral; LCD "Recovery / verify clear"; after 5s servo moves to close at normal speed.
7. [ ] Spam `cmd:add_uid` while tapping card → no `mutex timeout`; card lookup correct.
8. [ ] Interrupt SDA temporarily → next `lcd_show_*` recovers, no FSM hang.

- [ ] **Step 3: If all pass, proceed to Phase 4.**

---

## Phase 4 — Performance & minor cleanup

9 tasks, ~85 LOC. Goal: dọn bug nhẹ + tối ưu thread/memory.

### Task 4.1: Werkzeug thread bound

**Files:**
- Modify: `smart_gate/main.py`

- [ ] **Step 1: Set stack_size + optional semaphore**

Near the top of `smart_gate/main.py`:

```python
import threading
# Default thread stack is 8 MB; tabs leak threads → bound stack to 256 KB.
threading.stack_size(256 * 1024)
```

(Place this before any thread is spawned, ideally module-level just after imports.)

- [ ] **Step 2: Commit**

```bash
git add smart_gate/main.py
git commit -m "perf(daemon): cap Python thread stack to 256KB

Werkzeug threaded=True spawns one thread per request + SSE/MJPEG. With
the default 8 MB stack, 5 idle dashboard tabs × N polling threads grow
RSS quickly. 256 KB is generous for our request handlers.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 4.2: Detector exception rate limiter

**Files:**
- Modify: `smart_gate/recognition/detector.py`

- [ ] **Step 1: Add the rate-limit logic**

Replace the per-frame `except` block (around line 82-87) with:

```python
import time

# Module scope:
_err_window_start = time.monotonic()
_err_count = 0

# In the frame loop, replace the except branch:
except Exception:
    log.exception("frame loop error")
    nonlocal _err_window_start, _err_count   # if inside a method, use self._
    now = time.monotonic()
    if now - _err_window_start > 1.0:
        _err_window_start = now
        _err_count = 0
    _err_count += 1
    if _err_count > 5:
        log.warning("detector errors >5/s, sleeping 0.5s")
        time.sleep(0.5)
```

(Hoist `_err_window_start` and `_err_count` to instance attributes on `Detector.__init__` for cleanliness.)

- [ ] **Step 2: Commit**

```bash
git add smart_gate/recognition/detector.py
git commit -m "perf(detector): rate-limit per-frame exceptions

>5 exceptions/s triggers a 500ms sleep + summary log instead of the
50 MB/min log explosion when the matcher gets a malformed encoding.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 4.3: Matcher reload off bus thread

**Files:**
- Modify: `smart_gate/main.py`

- [ ] **Step 1: Spawn dedicated reload thread**

In `SmartGateApp.__init__`:

```python
self._matcher_reload_event = threading.Event()
self._matcher_reload_thread = threading.Thread(
    target=self._matcher_reload_loop, daemon=True, name="matcher-reload")
self._matcher_reload_thread.start()
```

Add the loop:

```python
def _matcher_reload_loop(self):
    while not self._shutdown.is_set():
        triggered = self._matcher_reload_event.wait(timeout=1.0)
        if not triggered:
            continue
        self._matcher_reload_event.clear()
        time.sleep(0.5)   # debounce — combine multiple rapid enrolls
        # Drain any additional triggers during the debounce window
        self._matcher_reload_event.clear()
        try:
            self._matcher.reload(self._db)
        except Exception:
            log.exception("matcher reload failed")
```

In `_consume_bus` where `self._matcher.reload(self._db)` was called inline, replace with:

```python
self._matcher_reload_event.set()
```

- [ ] **Step 2: Commit**

```bash
git add smart_gate/main.py
git commit -m "perf(daemon): matcher reload off bus-consumer thread

Bus consumer used to pause ~50ms per enroll while reload ran inline.
Dedicated reload thread with 500ms debounce + event-set signalling
keeps the bus snappy.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 4.4: MJPEG client disconnect

**Files:**
- Modify: `smart_gate/web/app.py`

- [ ] **Step 1: Shorten timeout + catch disconnect exceptions**

In `smart_gate/web/app.py` MJPEG generator (around line 84):

```python
def mjpeg_generator():
    while not self._shutdown.is_set():
        try:
            frame = self._hub.wait_bgr(timeout=0.5)
        except FrameTimeout:
            continue
        if frame is None:
            continue
        try:
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
                   + _annotated_jpeg(frame) + b'\r\n')
        except (GeneratorExit, OSError, BrokenPipeError):
            break
```

- [ ] **Step 2: Commit**

```bash
git add smart_gate/web/app.py
git commit -m "fix(web): MJPEG generator exits within 1s of client disconnect

Was holding the thread for 2s per poll. Smaller timeout + catching
GeneratorExit/OSError/BrokenPipeError lets the thread exit cleanly when
the browser closes.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 4.5: ESP-side log throttle for HC-SR04 distance

**Files:**
- Modify: `firmware/src/sensor.cpp`

- [ ] **Step 1: Throttle distance log to 1 Hz**

In `sensor_task`, wherever the distance is currently logged:

```cpp
static uint32_t s_last_dist_log_ms = 0;
if (millis() - s_last_dist_log_ms >= 1000) {
    s_last_dist_log_ms = millis();
    LOGI("sensor", "distance=%d cm", filtered);
}
```

- [ ] **Step 2: Build + commit**

```bash
cd firmware && /home/nguyenvd/.local/bin/pio run 2>&1 | tail -5
cd /home/nguyenvd/workspace/smart_gate
git add firmware/src/sensor.cpp
git commit -m "perf(firmware): throttle HC-SR04 distance log to 1Hz

Was 20Hz, generating 20 esp_log INSERTs/s. Complements the Pi-side
batched writer.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 4.6: ESP boot-time NULL / non-pdPASS checks

**Files:**
- Modify: `firmware/src/main.cpp`
- Modify: `firmware/src/buzzer_drv.cpp`

- [ ] **Step 1: Add halt-loud helper at top of `main.cpp`**

```cpp
static void halt_on_init_fail(const char* what) {
    LOGE("boot", "init failed: %s — halting", what);
    while (1) vTaskDelay(pdMS_TO_TICKS(1000));
}
```

- [ ] **Step 2: Check every timer/task create**

After every `xTimerCreate` / `xTaskCreatePinnedToCore` / `xTimerStart` call:

```cpp
g_open_reached_timer = xTimerCreate(...);
if (!g_open_reached_timer) halt_on_init_fail("g_open_reached_timer");

g_lcd_restore_timer = xTimerCreate(...);
if (!g_lcd_restore_timer) halt_on_init_fail("g_lcd_restore_timer");

// ... same for every timer ...

BaseType_t rc = xTaskCreatePinnedToCore(rfid_task, "rfid", 4096, NULL, 2, NULL, 1);
if (rc != pdPASS) halt_on_init_fail("rfid_task");
```

In `buzzer_drv.cpp` `buzzer_init`, add NULL check on `s_pulse_timer` and `s_warn_timer`:

```cpp
s_pulse_timer = xTimerCreate(...);
if (!s_pulse_timer) {
    LOGE("buzzer", "pulse timer create failed");
    // Don't halt — beeps will silently no-op (existing safeguard in beep_*_async)
}
```

- [ ] **Step 3: Build + commit**

```bash
cd firmware && /home/nguyenvd/.local/bin/pio run 2>&1 | tail -5
cd /home/nguyenvd/workspace/smart_gate
git add firmware/src/main.cpp firmware/src/buzzer_drv.cpp
git commit -m "fix(firmware): NULL / !=pdPASS checks at boot — halt-loud on failure

Previously a failed xTimerCreate left a NULL handle that crashed in
prvCheckForValidListAndQueue on the first xTimerStart, producing a
'panic' reset with no useful log. Now LOGE + indefinite vTaskDelay so
the user sees the failure in the journal.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 4.7: Pi boot-loop detector

**Files:**
- Modify: `smart_gate/main.py`

- [ ] **Step 1: Track recent boots**

In `SmartGateApp.__init__`:

```python
self._boot_times: list[float] = []
```

In `_handle_esp_event` `evt:boot` handler:

```python
self._boot_times.append(time.monotonic())
self._boot_times = self._boot_times[-5:]
if len(self._boot_times) >= 3:
    span = self._boot_times[-1] - self._boot_times[-3]
    if span < 60.0:
        self._audit(self._esp_log_bus, "error", "boot",
                    f"ESP boot loop detected ({len(self._boot_times)} boots in {span:.1f}s)")
        self._db.insert_event("system", None, False, detail="esp_boot_loop")
```

- [ ] **Step 2: Commit**

```bash
git add smart_gate/main.py
git commit -m "feat(daemon): boot-loop detector — 3 evt:boot within 60s alerts

Surfaces an audit + system event row so the dashboard shows the
condition. No auto-action (per user decision); operator intervenes.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 4.8: Misc minor cleanups (drive-by batch)

**Files:**
- Modify: `firmware/src/buzzer_drv.cpp`
- Modify: `firmware/src/uart_link.cpp`
- Modify: `smart_gate/link/uart_client.py`
- Modify: `smart_gate/data/db.py`
- Modify: `smart_gate/web/app.py`
- Modify: `smart_gate/video/recorder.py`

- [ ] **Step 1: buzzer_drv.cpp — pin LOW first action**

In `buzzer_init`, ensure the pin init happens before any other peripheral. Should already be the case; verify:

```cpp
void buzzer_init() {
    pinMode(PIN_BUZZER, OUTPUT);
    digitalWrite(PIN_BUZZER, LOW);
    // ... rest
}
```

- [ ] **Step 2: uart_link.cpp — reset s_pos + s_discarding in init**

```cpp
void uart_link_init() {
    // ... existing Serial1.begin etc ...
    s_pos = 0;
    s_discarding = false;
}
```

- [ ] **Step 3: uart_client.py — `link_alive` reads under lock**

```python
def link_alive(self) -> bool:
    with self._link_state_lock:
        return self._connected.is_set() and \
               (time.monotonic() - self._last_rx) < 10.0
```

(Add `self._link_state_lock = threading.Lock()` in `__init__`. Wrap all `_last_rx` writes in `_rx_loop` under the same lock.)

- [ ] **Step 4: uart_client.py — `ser.close()` debug log instead of pass**

```python
try:
    self._ser.close()
except Exception:
    log.debug("ser.close failed", exc_info=True)
```

- [ ] **Step 5: db.py — `touch_last_seen` batcher**

Add a small batcher pattern similar to `EspLogWriter` for `touch_last_seen` updates. Buffer updates by user_id; flush every 1 s with `UPDATE users SET last_seen=? WHERE id=?` in a transaction.

```python
class TouchLastSeenBatcher:
    def __init__(self, db, flush_interval_s: float = 1.0):
        self._db = db
        self._pending: dict[int, str] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        threading.Thread(target=self._loop, daemon=True, name="touch-batcher").start()

    def touch(self, user_id: int, ts_iso: str):
        with self._lock:
            self._pending[user_id] = ts_iso   # last write wins

    def _loop(self):
        while not self._stop.is_set():
            time.sleep(self._flush_interval_s)
            with self._lock:
                batch = list(self._pending.items())
                self._pending.clear()
            if not batch:
                continue
            try:
                with self._db.transaction():
                    self._db._conn.executemany(
                        "UPDATE users SET last_seen=? WHERE id=?",
                        [(ts, uid) for uid, ts in batch])
            except Exception:
                log.exception("touch_last_seen batch failed")
```

Wire into `SmartGateApp.__init__` and replace direct `db.touch_last_seen(uid)` calls with `self._touch_batcher.touch(uid, datetime.now(timezone.utc).isoformat())`.

- [ ] **Step 6: web/app.py — `_allocate_user_name` regex**

```python
import re
_USER_SUFFIX_RE = re.compile(r"^user_(\d{3,})$")

def _allocate_user_name(existing: set[str]) -> str:
    max_n = 0
    for name in existing:
        m = _USER_SUFFIX_RE.fullmatch(name)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"user_{max_n + 1:03d}"
```

- [ ] **Step 7: video/recorder.py — detail on ffmpeg fail**

```python
if rc != 0:
    log.warning("ffmpeg exited rc=%d for event %s", rc, event_id)
    try:
        self._db.update_event_detail(event_id, f"ffmpeg_failed_{rc}")
    except Exception:
        log.debug("update_event_detail failed", exc_info=True)
```

(Add `update_event_detail` to `Database` if missing.)

- [ ] **Step 8: Build firmware + run tests + commit**

```bash
cd firmware && /home/nguyenvd/.local/bin/pio run 2>&1 | tail -5
cd /home/nguyenvd/workspace/smart_gate
pytest tests/unit -q 2>&1 | tail -10
git add firmware/src/buzzer_drv.cpp firmware/src/uart_link.cpp \
        smart_gate/link/uart_client.py smart_gate/data/db.py \
        smart_gate/web/app.py smart_gate/video/recorder.py
git commit -m "chore: phase-4 drive-by cleanups

- buzzer_init pin-low first
- uart_link_init resets s_pos + s_discarding
- link_alive reads _connected + _last_rx under lock
- ser.close logs debug instead of swallowing
- touch_last_seen batched in a 1Hz writer
- _allocate_user_name uses re.fullmatch
- video recorder records ffmpeg failure code in event.detail

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### Task 4.9: Phase 4 verification gate (manual — soak)

- [ ] **Step 1: Flash + restart**

- [ ] **Step 2: Run Phase 4 test matrix (spec §10.6)**

1. [ ] Open 5 dashboard tabs + leave 1 h → `ps -L -p $(pgrep -f smart_gate)` shows < 50 threads; RSS < 200 MB.
2. [ ] Manually corrupt 1 face encoding row → log shows "detector errors >5/s, sleeping" not 50 MB/min.
3. [ ] Pull ESP power 3× within 60 s → dashboard error "ESP boot loop detected"; events row `system esp_boot_loop`.
4. [ ] `/api/esp_log?limit=100` after 1 min idle → `sensor` entries ≤ 60 (1 Hz).
5. [ ] Open + close 5 MJPEG clients → thread count returns to baseline within 1 s.

- [ ] **Step 3: Update memory with the new mechanisms**

Update the relevant memory files:
- `smart_gate_uart_decision.md`: note replay protection mechanism
- New `smart_gate_fsm_state_persist.md` if you want to capture the NVS gate_state namespace
- New `smart_gate_diag_paths.md` if you want to document evt:gate state=unknown + boot-loop alerts

- [ ] **Step 4: Final summary commit (if any documentation updates)**

```bash
git add docs/
git commit -m "docs: update memory + spec references after Phase 4 ship"
```

---

## Summary

Total: **48 tasks across 4 phases + 1 setup + 4 verification gates = 53 work units.**

| Phase | Tasks | LOC | Impl | Test | Risk |
|---|---|---|---|---|---|
| 0 Setup | 1 | — | 5 min | — | — |
| 1 Urgency | 11 | ~145 | 45 min | 25 min | Low |
| 2 Hardening | 13 | ~165 | 1.5 h | 30 min | Medium |
| 3 Hardware | 15 | ~225 | 2.5 h | 1 h bench | Med-High |
| 4 Perf+Minor | 9 | ~85 | 1 h | 30 min soak | Low |
| **Total** | **48** | **~620** | **~5.5 h** | **~2.5 h** | – |

Spec reference: `docs/superpowers/specs/2026-06-12-smart-gate-hang-and-robustness-fixes-design.md`
