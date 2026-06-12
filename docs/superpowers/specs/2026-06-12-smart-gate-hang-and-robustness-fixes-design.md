# Smart-gate hang fix + repo-wide robustness — design

**Date**: 2026-06-12
**Author**: brainstorming session w/ Claude Code
**Status**: design approved, ready for implementation plan
**Related**: continues from [`2026-05-21-smart-gate-architecture-design.md`](2026-05-21-smart-gate-architecture-design.md), [`2026-05-22-esp32-firmware-design.md`](2026-05-22-esp32-firmware-design.md), [`2026-05-22-pi-app-design.md`](2026-05-22-pi-app-design.md), [`2026-05-23-web-admin-design.md`](2026-05-23-web-admin-design.md)

## 1. Background

User report (2026-06-12): "đã chạy tốt, nhưng khi quẹt RFid bị treo ở access denied". After flashing the firmware via the Pi (workflow in `smart_gate_uart_decision.md`), `link_alive` became true and the system runs, but every rejected RFID scan leaves the LCD frozen on "Access denied" until the next granted swipe. The user requested a fix for that specific symptom plus a sweep for latent bugs across the entire repo.

Five review passes were run against the working tree (one direct hang investigation + four parallel adversarial reviewers with disjoint lenses: boot/init/error-recovery, hardware fault tolerance, UART protocol/security, Pi DB integrity & threading). Combined findings: **~14 critical + ~22 important + ~22 minor** issues.

The original hang is a Critical symptom but the surrounding issues represent significant latent risk (safety on brown-out, write-amplification on SD card, untrusted input handling, replay window on `cmd:open`, etc.). The user approved fixing everything except web authentication (explicit out-of-scope).

## 2. Goals & non-goals

**Goals**
- Eliminate the reported "access denied hang" so denied RFID swipes return the LCD to idle within 2.5 s.
- Close all Critical findings (except web auth) so no single fault hangs the gate or silently zombies the daemon.
- Close all Important findings that affect safety, data correctness, or operational visibility.
- Add UX-visible improvements requested mid-design: LCD presence icons (RFID + obstacle) in top-right corner; per-swipe I²C-status log line for debugging.
- Close Minor findings opportunistically when they live in files already being touched, otherwise defer.
- Structure the work as four phases so each can be reviewed, flashed, and verified independently. User can stop after any phase.

**Non-goals**
- Web admin authentication / CSRF / TLS — user explicitly skipped. Trust model remains "LAN-only, `/dev/serial0` restricted to `dialout` group".
- HMAC or cryptographic signing on `cmd:open` — same trust-model assumption; the only realistic attacker has physical access.
- Migration from Werkzeug dev server to a production WSGI server (waitress / gunicorn). Thread-count will be bounded instead.
- Rewriting HC-SR04 polling to use the ESP32 RMT peripheral or echo-edge ISR. Phase 4 only throttles the log rate.
- Schema migration of existing `events` rows — Phase 2 adds a version gate so future migrations work, but does not migrate current data.

## 3. Accepted residual risks

After all four phases ship, the following risks remain by design. They are documented so future operators know what is *not* mitigated.

1. **LAN-trust web UI**: any host on the LAN can `curl -X POST http://pi:8080/api/gate/open` and the gate opens. Mitigation depends on network segregation, not on the daemon.
2. **Local-process UART injection**: any process on the Pi belonging to group `dialout` can write to `/dev/serial0` and inject `cmd:open` (per-session sequence number bounded but recoverable by reading the last `evt:ack` from the wire). Mitigation is filesystem-permission discipline.
3. **Browser tab leak**: many concurrent dashboard tabs still leak threads — Phase 4 caps the per-thread stack to 256 KB so leak rate is slower, but real fix needs a different server.
4. **SD-card single point of failure**: Phase 2 reduces write rate from ~20 fsync/s to <5 fsync/s, but a worn-out SD eventually fails. No replication or remote-DB option in scope.

## 4. Success criteria

A run of the full verification suite (Section 10) must pass:
- RFID deny → LCD auto-restores to idle in 2.5 s.
- Brown-out mid-`S_OPENING` → on next boot, servo does **not** snap to close. Holds 90° neutral, emits `evt:gate state=unknown`.
- Fresh install missing `/etc/smart-gate/config.toml` → daemon logs a warning and uses `/dev/serial0` (not the obsolete `/dev/ttyUSB0`).
- 24-hour soak: `link_alive=true` continuously; RSS daemon < 200 MB; SD write IOPS < 5 in idle.
- `face_threshold` default in `packaging/config.default.toml` = `0.25` (matches the 2026-06-10 decision).
- 10-byte ISO 14443 UIDs render distinct across two cards sharing the first 7 bytes.
- Adversary feeding `1000 × 'A' + valid cmd:open\n` to `/dev/serial0` does **not** open the gate.
- DB migration 2 added to `migrations/0002_*.sql` runs once on first restart and is skipped on subsequent restarts.

## 5. Phase structure

Four sequential phases. Each phase is one commit, one verification gate, independently flashable, independently rollback-able.

| Phase | Theme | LOC | Impl | Test | Risk |
|---|---|---|---|---|---|
| **P1** | Urgency: hang fix, safety, config defaults, LCD icons | ~145 | 45 min | 25 min | Low |
| **P2** | Input hardening: UART overflow, replay, DB transactions, XSS | ~165 | 1.5 h | 30 min | Medium |
| **P3** | Hardware robustness: RFID health, sensor bounds, servo safety, brown-out recovery | ~225 | 2.5 h | 1 h bench | Med-high |
| **P4** | Performance + minor cleanup | ~85 | 1 h | 30 min soak | Low |
| **Total** | | **~620** | **~5.5 h** | **~2.5 h** | – |

Sequencing rationale: user-visible symptom first (P1), then close adversarial input surface before introducing more state (P2), then state-persisting hardware work that needs bench access (P3), then performance polish that benefits from earlier fixes already in place (P4).

## 6. Phase 1 — Urgency fixes

### 6.1 LCD restore timer (root cause of reported hang)

- `firmware/include/events.h`: add `EV_T_LCD_RESTORE` to `EventKind` enum.
- `firmware/src/main.cpp`: declare `TimerHandle_t g_lcd_restore_timer = nullptr;` and create one-shot 2500 ms timer in `setup()` with callback that posts `EV_T_LCD_RESTORE` to `g_event_q`.
- `firmware/src/gate_fsm.cpp`:
  - In the `EV_RFID_SCAN` deny branch (currently lines 244-248): after `lcd_show_denied()` and `buzzer_beep_err_async()`, call `xTimerChangePeriod(g_lcd_restore_timer, pdMS_TO_TICKS(2500), 0)` and `xTimerStart(g_lcd_restore_timer, 0)`.
  - Add dispatcher case for `EV_T_LCD_RESTORE`: `if (s_state == S_IDLE) lcd_show_idle();`. Guard prevents stomping an in-flight opening/closing message.

### 6.2 Buzzer non-blocking

- `firmware/src/buzzer_drv.{h,cpp}`: refactor `buzzer_beep_ok()` and `buzzer_beep_err()` into `buzzer_beep_ok_async()` and `buzzer_beep_err_async()`. Use a `TimerHandle_t s_pulse_timer` with an internal state machine (3-step for ok, 12-step for err) so the FSM task never blocks on `vTaskDelay`.
- All FSM call sites updated to use `_async` variants. Old blocking variants kept temporarily but marked deprecated, removed in P4 if no remaining callers.
- `buzzer_init()`: stop timer if already running so re-init is idempotent.

### 6.3 LCD presence icons (top-right corner)

Layout:

```
Col:    0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15
Row 0: [─── text area (14 chars) ────────────────] [O][R]
Row 1: [─── text area full 16 chars ────────────────────]
                                                   ↑   ↑
                                          obstacle│   │rfid
```

- Custom glyphs (`createChar` slot 0 = obstacle warning, slot 1 = RFID card) defined once in `lcd_init()`. 5×8 px each. Glyph constraints: obstacle = recognisable as triangle/warning silhouette filling ≥ 60 % of the cell; RFID = recognisable as a card/antenna silhouette filling ≥ 60 % of the cell. Final pixel bitmaps committed in source as `static const uint8_t` arrays.
- Row 0 text area shrinks to columns 0-13 (14 chars). Existing strings: "Smart Gate" (10), "Access denied" (13), "Opening..." (10) — all fit. Names rendered via `lcd_show_name` move to row 1 if longer than 14 chars.
- Refresh: `g_lcd_icon_timer` (periodic, 200 ms = 5 Hz) in `main.cpp`. Callback posts `EV_T_LCD_ICON_TICK` to FSM queue. Dispatcher case calls `lcd_update_icons(sensor_is_obstacle(), rfid_is_card_present())`.
- `lcd_update_icons` keeps `static bool s_last_obs, s_last_rfid;` and only writes to I²C when state actually changes — idle state produces zero I²C writes per second.
- Accessors:
  - `firmware/src/sensor.cpp`: add `static volatile bool s_obstacle_present;` set each sample. Expose `bool sensor_is_obstacle()`.
  - `firmware/src/rfid.cpp`: add `static volatile bool s_card_present;` set by RFID task right after `PICC_IsNewCardPresent()` returns true. Hold true for 300 ms after the last positive read (prevents flicker between poll cycles). Expose `bool rfid_is_card_present()`.

### 6.4 I²C diagnostic log on RFID swipe

- `firmware/src/lcd_drv.cpp`: `static int s_last_i2c_err = 0;` updated after each `lcd_show_*` sequence by checking `Wire.endTransmission()` return code at the end of the write block. Expose `int lcd_drv_last_i2c_err()`.
- `firmware/src/gate_fsm.cpp`, in the `EV_RFID_SCAN` handler immediately after `lcd_show_denied()` or `lcd_show_name()`:
  ```cpp
  int err = lcd_drv_last_i2c_err();
  if (err == 0) LOGI("i2c", "swipe uid=%s lcd_write ok", e.uid);
  else          LOGW("i2c", "swipe uid=%s lcd_write err=%d", e.uid, err);
  ```
- The 1 Hz log rate-limiter already in `log_emit.cpp` covers I²C log spam in the worst case. Always-on (no config flag in P1 — easy to add later if production noise warrants).

### 6.5 Pi-side audit-log for RFID denials

- `smart_gate/main.py:387-389` (`_handle_esp_event`, `kind == "evt:rfid"`, `granted == false`):
  ```python
  self._audit(self._esp_log_bus, "warn", "rfid",
              f"denied uid={uid[:8]}… name={name or '(unknown)'}")
  ```
- Surfaces in dashboard live-log + `esp_log` table. Was previously silent.

### 6.6 Config defaults sync

- `smart_gate/config.py:46`: `LinkCfg.port: str = "/dev/serial0"` (was `/dev/ttyUSB0`, pre-decision-#26).
- `smart_gate/config.py:111-112` (`load_config`): if `path.exists()` is False, emit `log.warning("config file %s not found, using defaults (link.port=%s)", path, cfg.link.port)` so the silent-fallback case is visible.
- `packaging/config.default.toml:13`: `face_threshold = 0.25` (was `0.55`, matches 2026-06-10 decision in `smart_gate_auth_priority` memory).

### 6.7 Timezone bug fix

- `smart_gate/web/app.py:106-112` and any other site using `datetime.now()` to filter SQLite columns: replace with `datetime.now(timezone.utc)`. SQLite `datetime('now')` writes UTC; the Flask filter was using local time, which in `Asia/Ho_Chi_Minh` (UTC+7) shifted the "today" boundary by 7 hours.
- Add `from datetime import timezone` where missing.

### 6.8 `_consume_bus` defensive wrap

- `smart_gate/main.py:168-194`: wrap the body of the `while not self._shutdown.is_set():` loop in `try / except Exception` with `log.exception(...)` plus a synthetic `_audit(..., "error", "internal", "bus consumer exception")` so the operator sees the failure on the dashboard. Add `time.sleep(0.5)` back-off to avoid a tight error loop.
- Daemon stays alive when the SD card flips read-only or DB write fails; operator gets a visible signal instead of a zombie process.

### 6.9 `_run_web` clean fail on port-in-use

- `smart_gate/main.py:409-426`: wrap `make_server(...)` and `serve_forever()` in `try / except OSError`. On bind failure (e.g. port 8080 already held), set `self._shutdown.set()` so the whole daemon exits non-zero and systemd restarts cleanly instead of running with a dead web thread.

### Phase 1 files changed

```
firmware/include/events.h                  (+2 enum: EV_T_LCD_RESTORE, EV_T_LCD_ICON_TICK)
firmware/src/main.cpp                      (+10 LOC, 2 new timers + callbacks)
firmware/src/gate_fsm.cpp                  (+20 LOC, deny arm + restore case + icon tick + i2c log)
firmware/src/buzzer_drv.h                  (+2 LOC, _async decls)
firmware/src/buzzer_drv.cpp                (+40 LOC, pulse timer refactor)
firmware/src/lcd_drv.{h,cpp}               (+35 LOC, createChar 2 glyph + lcd_update_icons + s_last_i2c_err)
firmware/src/sensor.{h,cpp}                (+5 LOC, s_obstacle_present + accessor)
firmware/src/rfid.{h,cpp}                  (+8 LOC, s_card_present + accessor + hold timer)
smart_gate/main.py                         (+15 LOC, audit deny + bus try/except + web try/except)
smart_gate/config.py                       (+3 LOC, port default + missing-config warning)
smart_gate/web/app.py                      (+5 LOC, TZ fix multiple sites)
packaging/config.default.toml              (1 line edit)
```

**LOC total**: ~145.

## 7. Phase 2 — Input hardening

### 7.1 ESP UART overflow tail discard

- `firmware/src/uart_link.cpp` (~line 22 + 121-127): introduce `static bool s_discarding = false;`. On `\n`: if discarding, reset and continue. On overflow (`s_pos >= UART_LINE_MAX - 1`): set `s_discarding = true`, emit `LOGW("uart","line overflow, discarding until next \\n")`, reset `s_pos = 0`. While discarding, drop bytes until the next `\n`.
- Fixes the existing exploit where 600 bytes of garbage followed by a valid JSON cmd would be parsed as if the cmd was clean.

### 7.2 Pi readline size cap

- `smart_gate/link/protocol.py`: add `MAX_LINE = 1024` constant (ESP `UART_LINE_MAX = 512`; double for margin).
- `smart_gate/link/uart_client.py:178`: replace `self._ser.readline()` with `self._ser.read_until(b"\n", size=protocol.MAX_LINE + 1)`. If returned bytes don't end in `\n`, log warning and discard (don't accumulate). Prevents unbounded RAM growth from a misbehaving / floating UART line.

### 7.3 TX-then-register race fix

- `smart_gate/link/uart_client.py:218-235`: in `_tx_loop`, register `self._pending[msg_id] = (ack_event, holder)` **before** calling `self._ser.write(payload)`. On write failure, pop the entry and signal the holder. Eliminates the race where an ESP ACK arrives sub-millisecond after the write and finds no registered pending — currently observed as spurious `LinkTimeout` after 2 s even though the gate physically opened.

### 7.4 `cmd:open` per-session replay protection

- `firmware/src/uart_link.cpp`: `static uint32_t s_last_cmd_id = 0;`.
- In `parse_line`, after JSON decode for `type == "cmd"`:
  - If `id == 0` or `id` is missing / non-numeric → `LOGW("uart","cmd missing/invalid id")`; return.
  - If `id <= s_last_cmd_id` → `LOGW("uart","cmd id %u replay (last=%u)", id, s_last_cmd_id)`; `emit_ack_err(id, "replay")`; return.
  - Else `s_last_cmd_id = id;` and proceed.
- Reset `s_last_cmd_id = 0` only on ESP boot (per-session). Pi side uses `itertools.count(int(time.time()))` instead of `count(1)` so IDs are monotonic across Pi restarts within the same ESP session.

### 7.5 innerHTML XSS escaping

- `smart_gate/web/templates/dashboard.html:255-258, 277-298`: route every dynamic field through the existing `escapeHtml()` helper (already in use by the toast renderer at lines 191-194). Apply to `state`, `last_user`, `r.name`, `r.id`, `r.error`, `r.qr_url`, and the raw `responseText` fallback. Use `textContent` for text-only fields, `escapeHtml()` for fields embedded in HTML structure.

### 7.6 Numeric query-param clamping

- `smart_gate/web/app.py`: add helper `_int_param(name, default, lo, hi)` that catches `TypeError/ValueError` (returns 400) and clamps to `[lo, hi]`. Apply at every `int(request.args.get(...))` site: `limit`, `after_id`, `before_id`, `last_id` (lines 95, 386, 92, 387, 400). Fixes the `?limit=-1` → "no LIMIT" full-table dump.

### 7.7 ESP-supplied name/uid length cap

- `smart_gate/main.py:379` (`_handle_esp_event` for `evt:rfid`): cap `name = (d.get("name") or "")[:32]` and `uid = (d.get("uid") or "")[:24]`. Matches ESP `e.name[32]` and the widened `e.uid[24]` (see 8.2). Defends downstream `log.info` and SQL bind from absurdly long input.

### 7.8 `doc["id"]` strict parsing

- `firmware/src/uart_link.cpp:32`: replace `e.cmd_id = (uint32_t)(doc["id"] | 0)` with explicit type check using ArduinoJson `JsonVariant::is<uint32_t>()`. Reject the cmd if missing or non-numeric. Prevents the buggy-Pi case where a missing `id` field gets silently treated as 0 and no ack ever returns.

### 7.9 DB migration version gate

- `smart_gate/data/db.py:41-47`: read `_meta.schema_version` (default 0 if missing). Iterate `[0-9]*.sql` files, skip any whose numeric prefix ≤ current. For each applicable file, run `executescript` and bump the meta row inside the same transaction. Logs the migration step.
- Prevents the future-migration bricking: today there is only `0001_init.sql` with `IF NOT EXISTS` so it's idempotent by accident, but adding `0002_*.sql` with an `ALTER TABLE ADD COLUMN` would crash on the second startup.

### 7.10 DB pragmas + transaction context manager

- `smart_gate/data/db.py` post-`connect()`:
  ```python
  self._conn.execute("PRAGMA journal_mode=WAL")
  self._conn.execute("PRAGMA synchronous=NORMAL")
  self._conn.execute("PRAGMA wal_autocheckpoint=1000")
  self._conn.execute("PRAGMA busy_timeout=5000")
  ```
- Add `transaction()` context manager that emits `BEGIN IMMEDIATE` / `COMMIT` (or `ROLLBACK` on exception).
- Multi-statement paths (`_handle_checkin` in `main.py` chains `insert_face_encoding` + `touch_last_seen` + `insert_event`) wrapped in `with self.db.transaction(): ...`.

### 7.11 ESP log batched writer

- New file `smart_gate/data/esp_log_writer.py`: class `EspLogWriter` with one daemon thread. `enqueue(row)` pushes into `deque(maxlen=10_000)` under a `Lock`. Worker loop waits on a `Condition` with 1 s timeout, then drains and writes up to 50 rows per `executemany`.
- `smart_gate/main.py:314`: replace `db.insert_esp_log(...)` with `self._esp_log_writer.enqueue(...)`. Reduces SD write rate from 20 fsync/s (the ESP log driver at 20 Hz) to roughly 1 fsync/s in idle.

### Phase 2 files changed

```
firmware/src/uart_link.cpp                 (+25 LOC, overflow + replay + id check)
smart_gate/link/protocol.py                (+1 LOC, MAX_LINE const)
smart_gate/link/uart_client.py             (+12 LOC, read_until size + TX register order + id init)
smart_gate/web/templates/dashboard.html    (~30 LOC edit, escape sites)
smart_gate/web/app.py                      (+15 LOC, _int_param helper + applies)
smart_gate/main.py                         (+8 LOC, name/uid cap + transaction wrap + writer wire)
smart_gate/data/db.py                      (+25 LOC, migration version + pragmas + transaction ctxmgr)
smart_gate/data/esp_log_writer.py          (+50 LOC, new file)
```

**LOC total**: ~165.

## 8. Phase 3 — Hardware robustness

### 8.1 MFRC522 health monitor

- `firmware/src/rfid.cpp`:
  - In `rfid_init()`, after `PCD_Init()`, read `PCD_ReadRegister(MFRC522::VersionReg)`. Expect `0x91` or `0x92`. On `0x00` / `0xFF` (floating MISO or held SPI line), set `static bool s_rfid_ok = false;` and emit `evt:log v="rfid_fault"` so `PeripheralTracker` flips RFID to `missing`.
  - `rfid_task`: every 60 s with no card, re-probe `VersionReg`. On drift: `PCD_Reset()`; `delay(50)`; `PCD_Init()`; re-probe. Rate-limit the `rfid_fault` emit to once per 5 minutes.
  - Per-UID rate-limit: `static char s_last_uid[24]; static uint32_t s_last_uid_ms;`. Same UID within 1 s of last queue-send → suppress (`PICC_HaltA` alone doesn't stop the same card being re-read 50 ms later if it stays on the antenna).

### 8.2 UID buffer widening

- `firmware/include/events.h`: `event_t.uid` from `char[16]` to `char[24]` (10-byte UID = 20 hex chars + NUL).
- `firmware/src/rfid.cpp:33`: `uid_hex[24]`. `uid_to_hex` bound check: `pos + 2 <= out_n - 1`. Validate `mfrc522.uid.size ∈ {4, 7, 10}`; drop other values with `LOGW`.
- Closes the 10-byte-UID collision where two DESFire cards sharing the first 7 bytes alias to the same allowlist entry.

### 8.3 HC-SR04 sane bounds + median filter

- `firmware/src/sensor.cpp`:
  - `setup`: `pinMode(PIN_SR04_ECHO, INPUT_PULLDOWN);` so a disconnected echo wire reads idle-low instead of floating.
  - `read_distance_cm()` bounds:
    ```cpp
    if (us == 0)     return -1;        // no echo
    if (us < 116)    return -1;        // < 2 cm impossible
    if (us > 23200)  return -1;        // > 400 cm: ghost
    ```
  - Median-of-3 over the last three valid reads — drops salt-pepper noise without significantly increasing latency.
  - FSM-side gate: don't believe `EV_PASSAGE_DETECTED` for the first 500 ms after `S_OPEN_WAIT` is entered (settles arm motion artefacts).
  - Fault notify: `static int s_no_echo_streak;` increments per no-echo sample, resets on a good sample. When `streak * 50 ms ≥ 30 s × 5` → emit one `evt:log v="sensor_fault"` per fault session.

### 8.4 Servo safety overhaul

- `firmware/include/config.h`: add `#define SERVO_MIN_PHYS_DEG 5` and `#define SERVO_MAX_PHYS_DEG 110` matching the mechanical design (FreeCAD spec).
- `firmware/src/servo_drv.cpp`:
  - `servo_set_angles(open_deg, close_deg)`: clamp to `[SERVO_MIN_PHYS_DEG, SERVO_MAX_PHYS_DEG]` (not `[0, 180]`).
  - New `servo_command_async(target_deg, on_reached_ms)`: attach servo, write target, arm `g_servo_detach_timer` (one-shot, period = expected travel ms + 200 ms margin). On fire: `s_servo.detach(); digitalWrite(PIN_SERVO, LOW);`. Saves idle power and reduces coil heat.
  - New `g_servo_stall_timer` (one-shot, 2× expected travel). If it fires before `EV_T_OPEN_REACHED` / `EV_T_CLOSE_REACHED`, emit `evt:log v="servo_stall"` and `force_close()`.
- `firmware/src/gate_fsm.cpp`: `start_open` / `start_closing` use `servo_command_async` and arm the stall timer.

### 8.5 Brown-out / panic / watchdog state persist

- New NVS namespace `gate_state` (separate from allowlist):
  - Keys: `last_state` (uint8_t = enum value), `last_ts` (uint32_t millis since boot).
- `firmware/src/gate_fsm.cpp`:
  - `enter_idle()`, `start_open()`, `S_OPEN_WAIT` entry, `S_TIMEOUT_WARN` entry, `start_closing()` → write `last_state` immediately after transition (~20 ms NVS write, acceptable inside the FSM task — measured no impact on FSM latency).
  - `gate_fsm_init()`:
    - Read `last_state` and the captured `reset_reason` (from `main.cpp` boot path).
    - If `reset_reason ∈ {brownout, panic, watchdog}` AND `last_state ∈ {S_OPENING, S_OPEN_WAIT, S_TIMEOUT_WARN, S_CLOSING}`:
      - Hold servo at **90° neutral** (mid-angle, avoids endpoint stress and avoids slamming an open gate closed).
      - Emit `evt:gate state=unknown reset_reason=<r>`.
      - After 5 s, fall through to `enter_idle()` which moves servo from 90° to `close_deg` at normal speed (not the snap-close that was previously immediate on every boot).
    - Else: normal `enter_idle()`.
- `smart_gate/main.py`: new handler for `evt:gate state=unknown` → audit log + dashboard banner. Operator-intervention only in P3; no new `cmd:reset_state` command is added in this work (the 5 s fall-through covers the safe-default path).

### 8.6 Allowlist mutex

- `firmware/src/allowlist.cpp`:
  - `static SemaphoreHandle_t s_mtx = nullptr;` created in `allowlist_init()`. Halt on NULL.
  - All `lookup` / `add` / `remove` / `list` / `count` ops wrapped:
    ```cpp
    if (xSemaphoreTake(s_mtx, pdMS_TO_TICKS(500)) != pdTRUE) {
        LOGW("allowlist","mutex timeout"); return -1;
    }
    // ... prefs op ...
    xSemaphoreGive(s_mtx);
    ```
  - `Preferences::begin()` return value captured. On false: `LOGE("nvs","allowlist begin failed");` set `s_degraded = true;` so lookups return `false` and `add` returns the existing NVS-fault error code.

### 8.7 LCD I²C bus recovery

- `firmware/src/lcd_drv.cpp`:
  - New `static bool i2c_recover_bus()` — bit-bang 9 SCL clock pulses + manual STOP if `Wire.endTransmission()` returns non-zero. Then `Wire.begin(...)` and `s_lcd.init()` to recover from a PCF8574 stuck-bus state.
  - Wrap `lcd_show_*` entries: before each sequence call `Wire.beginTransmission(LCD_ADDR); int rc = Wire.endTransmission();` as a probe. If `rc != 0` (NACK, bus error), call `i2c_recover_bus()` then `s_lcd.init()`, retry the probe once; if still failing, set `s_last_i2c_err = rc` and return without writing (caller observes via `lcd_drv_last_i2c_err()`).
  - Moving LCD writes off the FSM task to a dedicated low-priority task is **out of scope for P3** (would change the threading model significantly) — Phase 3 minimal is recovery + bus check.

### Phase 3 files changed

```
firmware/include/events.h                  (+1 LOC, uid array size)
firmware/include/config.h                  (+2 LOC, SERVO_MIN/MAX_PHYS_DEG)
firmware/src/rfid.cpp                      (+50 LOC, version probe + rate limit + 10-byte uid)
firmware/src/sensor.cpp                    (+30 LOC, bounds + median + fault streak)
firmware/src/servo_drv.cpp                 (+40 LOC, async command + detach + stall timer)
firmware/src/gate_fsm.cpp                  (+35 LOC, state persist + brown-out handling + servo_command_async)
firmware/src/allowlist.cpp                 (+25 LOC, mutex + begin check)
firmware/src/lcd_drv.cpp                   (+30 LOC, i2c recovery + wrap)
firmware/src/main.cpp                      (+5 LOC, new timers)
smart_gate/main.py                         (+8 LOC, evt:gate state=unknown handler)
```

**LOC total**: ~225.

## 9. Phase 4 — Performance & minor cleanup

### 9.1 Werkzeug thread bound

- `smart_gate/main.py:421` before spawning the server:
  ```python
  import threading
  threading.stack_size(256 * 1024)   # default 8 MB → 256 KB per thread
  ```
- Optional: `threading.Semaphore(8)` to cap concurrent SSE/MJPEG clients with 503 on overflow. Compromise — a proper async server is out of scope.

### 9.2 Detector exception rate limiter

- `smart_gate/recognition/detector.py:82-87`: track exceptions in a 1-second sliding window. After 5 in a window, sleep 0.5 s and log a single summary line. Caps the 50 MB/min log explosion when the matcher gets a malformed encoding.

### 9.3 Matcher reload off the bus-consumer thread

- `smart_gate/main.py`: spawn a single dedicated `_matcher_reload_thread` (daemon, event-driven). Bus consumer just `set()`s the event. Reload thread debounces 500 ms (combines multiple rapid enrolls). Removes the ~50 ms hiccup the bus consumer would otherwise pay per enroll.

### 9.4 MJPEG client disconnect

- `smart_gate/web/app.py:84`: reduce hub wait timeout to 0.5 s; catch `GeneratorExit / OSError / BrokenPipeError` and break. Threads exit within 1 s of client disconnect instead of holding until the next frame.

### 9.5 ESP-side log throttle (HC-SR04 distance)

- `firmware/src/sensor.cpp`: throttle distance log from 20 Hz to 1 Hz with `static uint32_t s_last_log_ms;`. "No echo" warning at 30 s stays. Major UART traffic reduction; complements Phase 2 batched writer.

### 9.6 NULL / non-pdPASS checks at boot

- `firmware/src/main.cpp:88-109` and `firmware/src/buzzer_drv.cpp:18`: capture return values of every `xTimerCreate`, `xTaskCreatePinnedToCore`, `xTimerStart`, `Preferences::begin`. On NULL or `!= pdPASS`: `LOGE("boot","init failed: <name>"); while(1) vTaskDelay(...);`. Loud halt instead of silent zombie task / phantom timer.

### 9.7 Pi-side boot-loop detector

- `smart_gate/main.py:371` (`evt:boot` handler): keep a rolling list of the last 5 boot timestamps. If 3+ boots within 60 s, emit `_audit(... "error", "boot", "ESP boot loop detected (N boots in T s)")` and insert a system event row. Surface only — operator intervenes (per user decision; no auto-cooldown of cmd:open).

### 9.8 Misc minor cleanups (drive-by while touching neighbouring files)

| Site | Fix |
|---|---|
| `firmware/src/buzzer_drv.cpp:17` | `pinMode + digitalWrite(LOW)` is the first action in `setup()`, before any other peripherals init |
| `smart_gate/link/uart_client.py:101-103` | `link_alive()` reads `_connected` and `_last_rx` under the same lock |
| `smart_gate/data/db.py:79` | `touch_last_seen` batched via a background writer (same pattern as `esp_log_writer`), flush 1 s |
| `smart_gate/video/recorder.py:96` | Update event row with `detail=ffmpeg_failed_<code>` when clip write fails |
| `smart_gate/link/uart_client.py:200` | `except Exception: log.debug(...)` on `ser.close()` instead of `pass` |
| `smart_gate/web/app.py:443` | `_allocate_user_name` uses `re.fullmatch` instead of `IndexError`-on-truncate |
| `firmware/src/uart_link.cpp:22` | `s_pos = 0; s_discarding = false;` in `uart_link_init()` for soft-reboot cleanliness |

### Phase 4 files changed

```
firmware/src/main.cpp                      (+8 LOC, NULL checks halt-loud)
firmware/src/buzzer_drv.cpp                (+2 LOC, timer NULL + pin init order)
firmware/src/sensor.cpp                    (+5 LOC, log throttle)
firmware/src/uart_link.cpp                 (+2 LOC, init reset)
firmware/src/allowlist.cpp                 (+3 LOC, begin check)
smart_gate/main.py                         (+25 LOC, boot-loop detect + matcher thread)
smart_gate/recognition/detector.py         (+10 LOC, err rate limit)
smart_gate/web/app.py                      (+5 LOC, MJPEG disconnect)
smart_gate/data/db.py                      (+15 LOC, touch_last_seen batcher)
smart_gate/link/uart_client.py             (+5 LOC, link_alive lock + ser.close log)
smart_gate/video/recorder.py               (+3 LOC, detail on ffmpeg fail)
```

**LOC total**: ~85.

## 10. Verification strategy

### 10.1 Baseline (run before P1 begins, save for diff)

- `iostat -dx 1 /dev/mmcblk0` — 60 s, capture write IOPS
- `ps -L -p $(pgrep -f smart_gate)` — thread count
- `curl http://127.0.0.1:8080/healthz?format=json` — `link_alive`, `uptime`
- `curl http://127.0.0.1:8080/api/esp_log?limit=10` — last 10 events
- `ssh pi 'sudo journalctl -u smart-gate --since "1 min ago" | wc -l'` — log volume
- Manual: 1 enrolled card swipe + 1 deny swipe → observe LCD + Pi audit

### 10.2 Per-phase verify gates

| Metric | Pre-P1 | Post-P1 | Post-P2 | Post-P3 | Post-P4 |
|---|---|---|---|---|---|
| LCD restores after deny | ✗ | ✓ | ✓ | ✓ | ✓ |
| Pi audit shows denial | ✗ | ✓ | ✓ | ✓ | ✓ |
| Fresh-install link port correct | ✗ | ✓ | ✓ | ✓ | ✓ |
| Replay `cmd:open` blocked | ✗ | ✗ | ✓ | ✓ | ✓ |
| Garbage-prefix exploit blocked | ✗ | ✗ | ✓ | ✓ | ✓ |
| Negative `?limit=-1` returns 400 | ✗ | ✗ | ✓ | ✓ | ✓ |
| SD write IOPS idle | ~20 | ~20 | < 5 | < 5 | < 3 |
| 10-byte UID distinct | ✗ alias | ✗ | ✗ | ✓ | ✓ |
| Brown-out servo behaviour | snap | snap | snap | neutral hold | neutral |
| RSS daemon (5 tabs, 1 h) | growing | grow | grow | grow | bounded < 200 MB |
| ESP-boot-loop alert visible | ✗ | ✗ | ✗ | ✗ | ✓ |

### 10.3 Phase 1 concrete tests

1. Build + flash from Pi (workflow in `smart_gate_uart_decision.md`); `sudo systemctl restart smart-gate`.
2. Swipe an un-enrolled card 5 times in a row → LCD returns to "Smart Gate / Ready" 2.5 s after each. Dashboard `/api/esp_log` shows 5 `warn rfid denied` lines.
3. Swipe deny then swipe granted *during* the buzzer pattern → gate opens immediately (FSM not stalled).
4. SSH Pi, `sudo mv /etc/smart-gate/config.toml /tmp/; sudo systemctl restart smart-gate; sudo journalctl -u smart-gate --since "1 min ago" | grep -i "config file"` → WARNING + port `/dev/serial0`. Restore config.
5. `grep face_threshold packaging/config.default.toml` → `0.25`.
6. Query `/events.json?range=today` near local midnight → events before UTC midnight don't appear.
7. Place hand in front of HC-SR04 → obstacle icon at col 14 row 0 appears; remove → disappears. Place card on RFID antenna → RFID icon at col 15 appears; lift → disappears after 300 ms hold.
8. Each swipe writes `info i2c swipe uid=... lcd_write ok` to live-log. Loosen SDA temporarily → next swipe shows `warn i2c swipe ... lcd_write err=N`.
9. Idle 30 s with no swipe and no obstacle → no `lcd_write` log lines (state-change-only icon refresh).

### 10.4 Phase 2 concrete tests

1. `printf '{"type":"cmd","v":"open","id":1}\n' | sudo tee /dev/serial0` → gate opens. Repeat → does **not** open (replay rejected).
2. `python -c "import sys; sys.stdout.buffer.write(b'A'*1000 + b'{\"type\":\"cmd\",\"v\":\"open\",\"id\":2}\n'); sys.stdout.flush()" | sudo tee /dev/serial0` → does **not** open (tail discard).
3. Fake-ESP pumping non-`\n` bytes for 10 s → daemon RSS does not grow > 50 MB.
4. 100 concurrent `/api/gate/state.json` polls + 10 `/api/gate/open` → all ACK, no `LinkTimeout` in journal.
5. Enroll user with name `<img src=x onerror=alert(1)>` → dashboard renders literal text, no alert.
6. `curl 'http://pi:8080/events.json?limit=-1'` → HTTP 400.
7. Add `migrations/0002_test.sql` with `CREATE TABLE test_v2 (id INT);` → first restart logs "migrated to 2"; second restart skips.
8. `iostat -dx 1 /dev/mmcblk0` over 60 s in idle → write IOPS < 5.

### 10.5 Phase 3 concrete tests (bench, needs hardware access)

1. Unplug MISO on RFID → restart ESP → log `MFRC522 init failed version=0x00`; dashboard PeripheralTracker flips RFID → `missing`. Re-plug + tap card → still `missing` until 60 s soft-reset cycle, then recovers.
2. (If available) DESFire 10-byte card → `evt:rfid uid=...` shows 20 hex chars, not truncated.
3. Unplug ECHO wire → after 30 s log "no echo for 30s"; after 150 s log "sensor_fault"; gate still closes via passage_timeout slow path; peripheral status `missing`.
4. Hold arm physically still while gate is opening → within 2× expected travel (~1.2 s) emit `servo_stall` + arm returns to `close_deg` + LCD shows error.
5. Send `cmd:config servo_open_deg=180` from web → Pi accepts but ESP clamps to 110°; arm does not over-travel.
6. Open gate, mid-rise pull power on both Pi and ESP → power back → ESP boot reads `reset_reason=brownout, last_state=S_OPENING` → servo holds 90° neutral; LCD shows "Recovery — verify clear"; after 5 s without manual override servo moves to close at normal speed.
7. Spam `cmd:add_uid` from web while tapping a card in another hand → no `mutex timeout` log; card lookup still correct.
8. Temporarily interrupt SDA → next `lcd_show_*` triggers recovery routine, succeeds, no FSM hang.

### 10.6 Phase 4 concrete tests

1. Open 5 dashboard tabs + leave 1 h → `ps -L -p $(pgrep -f smart_gate)` thread count < 50; RSS < 200 MB.
2. Corrupt 1 face encoding row in DB → log shows "detector errors >5/s, sleeping" instead of 50 MB/min.
3. Pull power on ESP 3 times within 60 s → dashboard live-log shows `error boot ESP boot loop detected`; `events` table contains `system esp_boot_loop` row.
4. `/api/esp_log?limit=100` after 1 minute idle → `sensor` entries ≤ 60 (1 Hz).
5. Open 5 MJPEG clients + immediately close → thread count returns to baseline within 1 s.

## 11. Risk & rollback

| Phase | Highest risk | Detection | Rollback |
|---|---|---|---|
| **P1** | Custom glyph renders as garbage at col 14/15 | Visual check immediately | `git revert` P1 commit; flash binary cached at `.pio/build/esp32dev/firmware.bin` from earlier build |
| **P2** | DB transaction context manager wraps incorrectly → held transaction → SQLITE_BUSY storm | `journalctl | grep SQLITE_BUSY`; write IOPS spike | `git revert` `data/db.py` + `main.py` insert sites; the ESP log writer thread is independent and stays in place |
| **P3** | NVS `gate_state` write or read fails → boot logic acts on garbage → unpredictable servo behaviour | First-boot ESP serial log shows `nvs gate_state read=...`; halt early on read failure | `nvs_erase_namespace("gate_state")` over USB-C serial console; firmware has a fallback path to plain `enter_idle()` when key is missing |
| **P4** | `threading.stack_size(256k)` insufficient for a recursion case → random `RecursionError` | 1 h soak test | `git revert` the single LOC; restart daemon |

Each phase is one commit. Reverting one phase does not affect earlier phases. Memory updates happen *after* the verify gate passes, not before, so a reverted phase doesn't leave stale memory entries.

## 12. Implementation tactics

- One commit per phase. Commit message format: `feat(safety): phase N — <one-liner>`.
- Verify on real Pi + ESP after each phase before moving on. Do not stack two phases without a verify in between — debugging is much harder with two stacked.
- Pause points are at phase boundaries. Within a phase, complete the phase before stopping.
- Memory update after a phase passes verification: add facts about new NVS namespace (P3), new replay counter (P2), new icon mechanism (P1), boot-loop detector (P4). Use the `smart-gate-*` namespace consistently.

## 13. Appendix — full findings catalog

Categorised list of every finding from the 5-pass review, with the phase that addresses it. Items are file:line at the time of review; line numbers may shift slightly during implementation.

### 13.1 Critical (addressed)

1. `firmware/src/gate_fsm.cpp:244` — LCD restore timer missing → P1 §6.1
2. `smart_gate/config.py:46` — `LinkCfg.port` default obsolete → P1 §6.6
3. `firmware/src/uart_link.cpp:121` — Line-overflow tail accepted → P2 §7.1
4. `smart_gate/link/uart_client.py:178` — `readline()` no size cap → P2 §7.2
5. `firmware/src/uart_link.cpp:23-74` — No replay protection on `cmd:open` → P2 §7.4
6. `smart_gate/link/uart_client.py:218` — TX-then-register race → P2 §7.3
7. `smart_gate/main.py:314` — `evt:log` synchronous INSERT per line → P2 §7.11
8. `smart_gate/data/db.py:41` — `migrate()` no version gate → P2 §7.9
9. `smart_gate/main.py:168-194` — `_consume_bus` no try/except → P1 §6.8
10. `firmware/src/main.cpp:88-92` — `xTimerCreate` NULL deref → P4 §9.6
11. `firmware/src/sensor.cpp:8-17` — Floating ECHO ghost reading → P3 §8.3
12. `firmware/src/rfid.cpp:11-25` — MFRC522 no version probe → P3 §8.1
13. `firmware/src/rfid.cpp:33` — UID buffer truncates 10-byte → P3 §8.2
14. `smart_gate/web/app.py:150-219` — Web admin no auth → **out of scope** (§3 risk #1)

### 13.2 Important (addressed)

15. `firmware/src/buzzer_drv.cpp:27-34` — Blocking 360 ms err beep → P1 §6.2
16. `firmware/src/buzzer_drv.cpp:21-25` — Blocking 80 ms ok beep → P1 §6.2
17. `firmware/src/allowlist.cpp:7` — `Preferences prefs` no mutex → P3 §8.6
18. `firmware/src/servo_drv.cpp:9-23` — Servo permanently attached, no stall → P3 §8.4
19. `firmware/src/lcd_drv.cpp:8-18` — No I²C bus recovery → P3 §8.7
20. `firmware/src/sensor.cpp:14` — No max-range bound, ghost echoes → P3 §8.3
21. `firmware/src/gate_fsm.cpp:175-176, 254-255` — Per-RFID timer reset open-extend exploit → P3 §8.1 (rate-limit) + §8.3 (FSM gate)
22. `firmware/src/gate_fsm.cpp:322` — Boot snaps servo close after brown-out → P3 §8.5
23. `firmware/src/main.cpp:103-106` — `xTaskCreate` return ignored → P4 §9.6
24. `firmware/src/allowlist.cpp:23, gate_fsm.cpp:316` — `Preferences::begin` ignored → P3 §8.6 + P4 §9.6
25. `firmware/src/uart_link.cpp:103-105` — RX buffer 256 B vs cmd up to 512 → P4 §9.6 (documented as risk; resize attempt is fragile per existing comment)
26. `smart_gate/main.py:409-426` — `_run_web` no try/except → P1 §6.9
27. `smart_gate/web/templates/dashboard.html:255-258, 277-298` — innerHTML XSS → P2 §7.5
28. `smart_gate/web/app.py:95, 386` — Negative `limit` bypasses pagination → P2 §7.6
29. `smart_gate/main.py:375-389` — Pi silent on RFID denial → P1 §6.5
30. `smart_gate/web/app.py:218, 302` — DB writes in Flask without try/except → P4 §9.8 (audit row on fail)
31. `smart_gate/main.py:421` — Werkzeug `threaded=True` unbounded → P4 §9.1
32. `smart_gate/web/app.py:395-429` — SSE bus condition lock with N subscribers → P4 §9.4 (related — MJPEG fix; SSE follows same pattern)
33. `smart_gate/main.py:248-251` — Auto-enroll vs matcher reload race → P4 §9.3 (off bus thread)
34. `smart_gate/recognition/detector.py:82-87` — Exception swallow per-frame → P4 §9.2
35. `smart_gate/recognition/matcher.py:20-31` — `Matcher.reload` on bus thread → P4 §9.3
36. `smart_gate/web/app.py:84` — MJPEG client disconnect leaks thread → P4 §9.4

### 13.3 Minor (addressed)

*Catalog is non-exhaustive: the brainstorming session aggregated ~22 minor items. The list below covers the meaningful ones; the rest are drive-by cleanups absorbed into Phase 4 §9.8 without separate enumeration.*


37. `packaging/config.default.toml:13` — `face_threshold = 0.55` ≠ memory 0.25 → P1 §6.6
38. `smart_gate/web/app.py:106-112` — TZ-naive datetime filter → P1 §6.7
39. `firmware/src/uart_link.cpp:32` — `doc["id"] | 0` silent → P2 §7.8
40. `smart_gate/main.py:379` — ESP-supplied name no length cap → P2 §7.7
41. `firmware/src/gate_fsm.cpp:106-119` — `handle_list` truncates silently → P3 §8.6 (page or error)
42. `firmware/src/uart_link.cpp:22-23` — `s_linebuf` no reset on init → P4 §9.8
43. `firmware/src/buzzer_drv.cpp:18` — Buzzer warn timer unchecked → P4 §9.6
44. `firmware/src/main.cpp:60-61` — GPIO2 strapping pin nuance, LED status only at end of setup → P4 §9.6 (add phase blinks if time permits)
45. `firmware/src/sensor.cpp:39-43` — No "sensor_fault" notify to Pi → P3 §8.3
46. `smart_gate/link/uart_client.py:101-103` — `link_alive` non-atomic compound read → P4 §9.8
47. `smart_gate/data/db.py:79` — `touch_last_seen` fire-and-forget per grant → P4 §9.8 (batcher)
48. `smart_gate/main.py:155` — Signal-install ValueError silently downgraded → kept as-is (not actionable)
49. `smart_gate/video/recorder.py:55, 96` — Exception swallowed; clip-fail no detail → P4 §9.8
50. `smart_gate/link/uart_client.py:200` — `ser.close()` `except Exception: pass` → P4 §9.8
51. `smart_gate/web/app.py:443` — `_allocate_user_name` IndexError prone → P4 §9.8

### 13.4 Not addressed in this work (deferred or out-of-scope)

- Web admin authentication / CSRF / TLS — §3 risk #1, user-skipped.
- HMAC on `cmd:open` — §3 risk #2, accepted trust model.
- `Preferences prefs` namespace cross-talk between allowlist and config — limited blast radius after §8.6 mutex; deferred.
- Camera capture loop memory model — not reviewed in depth; future audit if RSS growth observed.
- `firmware/src/lcd_drv.cpp` move to dedicated task — §8.7 keeps writes on FSM task; future refactor if WDT panics re-appear.
- Schema migration of existing rows — §7.9 only adds the gate, not a retroactive migration.
