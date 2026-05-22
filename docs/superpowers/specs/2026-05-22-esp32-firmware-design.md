# Smart Gate — ESP32 Firmware Design Spec

**Date:** 2026-05-22 (revised 2026-05-23: UART transport pivoted to GPIO UART1)
**Session:** dev_esp (ESP32 firmware)
**Status:** Design draft awaiting review
**Consumes:** [`2026-05-21-smart-gate-architecture-design.md`](2026-05-21-smart-gate-architecture-design.md) — sections §4 (UART protocol) and §5 (pin assignment) are authoritative.
**Scope:** This spec covers the ESP32 firmware deliverable: PlatformIO project layout, FreeRTOS task model, module breakdown, NVS allowlist schema, error/logging/watchdog handling, manual test scenarios, and build/flash workflow. Pi-side code, KiCad/FreeCAD work, and architectural changes are out of scope and must be raised in their respective sessions.

---

## 1. Overview

The ESP32 firmware is a FreeRTOS application running on an ESP32-WROOM-32 DevKit, talking to a Raspberry Pi over a **3-wire GPIO UART link** — ESP32 **UART1** on GPIO 32 (RX) / GPIO 25 (TX) ↔ Pi GPIO header pins 8/10 (BCM 14/15) — using the JSON Lines protocol defined in the architecture spec §4 (decision #26, 2026-05-23). UART0 (GPIO 1/3, USB-CDC) is reserved for `pio device monitor` debug and `esptool.py` firmware flashing — not for runtime app comm. It manages five peripherals — RC522 RFID reader, SG90 servo (barrier arm), LCD 20×4 (I2C), HC-SR04 ultrasonic passage sensor, and an active buzzer — and operates the barrier gate independently of the Pi link, with an NVS-stored RFID allowlist.

Design goals, in order:

1. **Spec compliance.** Implement the UART protocol exactly (§4.2 framing, §4.3 command verbs, §4.4 event verbs, §4.5 state machine). Use the pin assignment from §5 verbatim.
2. **Standalone resilience.** The gate must work when the Pi is disconnected; RFID auth is local.
3. **Simplicity over scalability.** This is a prototype: four FreeRTOS tasks, not seven. Inline actuator drives over per-peripheral tasks where the I/O is non-blocking.
4. **Observability.** Every state transition and error path emits a serial event so the Pi (and the human at the Pi monitor) can see what is happening.

---

## 2. Toolchain & libraries

- **Framework:** Arduino-ESP32 (via PlatformIO).
- **Board:** `esp32dev` (generic ESP32 DevKit, WROOM-32).
- **Reasoning:** Arduino-ESP32 gives access to FreeRTOS primitives directly (`xQueueCreate`, `xTaskCreatePinnedToCore`, `xTimerCreate`) while keeping the library ecosystem (MFRC522, LiquidCrystal_I2C, ESP32Servo) easy. ESP-IDF was considered and rejected because the peripheral driver porting cost outweighs its low-level control benefits for a five-peripheral prototype.

### 2.1 Dependencies (`platformio.ini` `lib_deps`)

| Library | Version | Purpose |
| --- | --- | --- |
| `bblanchon/ArduinoJson` | `^7.0` | JSON Lines parse + serialize. Static document allocation to avoid heap fragmentation. |
| `miguelbalboa/MFRC522` | `^1.4` | RC522 SPI driver. Supports both polling and IRQ; we use polling for simplicity (50 ms loop). |
| `madhephaestus/ESP32Servo` | `^3.0` | LEDC-backed 50 Hz PWM. Provides `Servo::write(angle)` API used by `servo_drv`. |
| `marcoschwartz/LiquidCrystal_I2C` | `^1.1` | PCF8574 backpack LCD; print + cursor positioning. |

No library is used for HC-SR04 (10-line `pulseIn` implementation in `sensor.cpp`) or NVS (Arduino-ESP32 bundles `Preferences.h`).

### 2.2 `platformio.ini`

```ini
[env:esp32dev]
platform = espressif32@^6.0
board = esp32dev
framework = arduino
monitor_speed = 115200
upload_speed = 921600
upload_port = /dev/ttyUSB0
monitor_port = /dev/ttyUSB0
build_flags =
    -D CORE_DEBUG_LEVEL=3
    -D FW_VERSION=\"1.0.0\"
    -D ARDUINOJSON_USE_LONG_LONG=1
lib_deps =
    bblanchon/ArduinoJson@^7.0
    miguelbalboa/MFRC522@^1.4
    madhephaestus/ESP32Servo@^3.0
    marcoschwartz/LiquidCrystal_I2C@^1.1
```

The Pi-side `pyserial` consumer must `close()` `/dev/ttyUSB0` during `pio run -t upload`; the architecture spec §4.1 already calls this out.

---

## 3. Project layout

```
firmware/
├── platformio.ini
├── include/
│   ├── config.h          # Pin numbers (from architecture §5), timings, sizes
│   ├── events.h          # event_t, outbound_msg_t, enums
│   └── version.h         # FW_VERSION
├── src/
│   ├── main.cpp          # setup(): NVS, queues, timers, tasks. loop() empty.
│   ├── uart_link.cpp/.h  # JSON Lines RX/TX, parser, ack helper
│   ├── rfid.cpp/.h       # MFRC522 polling task, allowlist lookup
│   ├── sensor.cpp/.h     # HC-SR04 polling task, debounce
│   ├── gate_fsm.cpp/.h   # state machine, timer callbacks
│   ├── servo_drv.cpp/.h  # open_now() / close_now() (inline driver)
│   ├── lcd_drv.cpp/.h    # show_idle() / show_name() / show_warn() (inline)
│   ├── buzzer_drv.cpp/.h # beep_ok() / beep_err() / pattern_warn() (inline)
│   └── allowlist.cpp/.h  # NVS-backed UID/name store
├── README.md             # Pin map, build & flash, troubleshooting
└── test/                 # (empty for MVP — see §10)
```

`include/` is for headers shared across translation units; `src/*.h` files stay next to their `.cpp` to keep module-local types out of the public include path.

---

## 4. Configuration constants (`include/config.h`)

```cpp
// Pin assignments (mirror architecture spec §5)
#define PIN_LED_STATUS   2
#define PIN_RC522_CS     5
#define PIN_RC522_SCK    18
#define PIN_RC522_MISO   19
#define PIN_RC522_MOSI   23
#define PIN_RC522_RST    17
#define PIN_RC522_IRQ    16   // reserved; polling mode in MVP
#define PIN_LCD_SDA      21
#define PIN_LCD_SCL      22
#define PIN_SR04_TRIG    27
#define PIN_SR04_ECHO    26
#define PIN_SERVO        13
#define PIN_BUZZER       14

// Pi UART link on ESP32 UART1 routed via GPIO matrix (decision #26, 2026-05-23).
// Pi pin 8 (BCM14, TX0) → GPIO 32; Pi pin 10 (BCM15, RX0) ← GPIO 25.
// UART0 (GPIO 1/3) stays for `pio device monitor` debug + esptool flashing.
#define PIN_PI_UART_RX   32
#define PIN_PI_UART_TX   25

// Timings (ms) — defaults; overridable via cmd:config
#define DEFAULT_OPEN_REACHED_MS    300   // SG90 sweep time
#define DEFAULT_CLOSE_REACHED_MS   300
#define DEFAULT_PASSAGE_TIMEOUT_MS 10000
#define DEFAULT_WARN_GIVEUP_MS     5000
#define HEARTBEAT_INTERVAL_MS      10000
#define RFID_POLL_INTERVAL_MS      50
#define SENSOR_POLL_INTERVAL_MS    50
#define SENSOR_DEBOUNCE_COUNT      3
#define SENSOR_TRIGGER_CM          25     // person "in range" threshold

// Servo angles — defaults; overridable
#define DEFAULT_SERVO_OPEN_DEG     100
#define DEFAULT_SERVO_CLOSE_DEG    10

// LCD I2C address (PCF8574 backpack — usually 0x27 or 0x3F)
#define LCD_I2C_ADDR              0x27
#define LCD_COLS                  20
#define LCD_ROWS                  4

// NVS
#define NVS_NS_ALLOWLIST          "allowlist"
#define NVS_NS_CONFIG             "config"
#define NVS_INDEX_KEY             "_index"
#define ALLOWLIST_MAX_ENTRIES     100

// UART / JSON
#define UART_BAUD                 115200
#define UART_LINE_MAX             512
#define JSON_DOC_CAPACITY         768
#define EVENT_QUEUE_LEN           16
#define OUTBOUND_QUEUE_LEN        16
```

All tunables live here so the `config.h` diff is the only place a reviewer must look to verify pin/timing conformance with the architecture spec.

---

## 5. Event types (`include/events.h`)

```cpp
enum EventSrc : uint8_t { SRC_UART, SRC_RFID, SRC_SENSOR, SRC_TIMER };

enum EventKind : uint8_t {
  // Commands from Pi (parsed in uart_link, dispatched as events)
  EV_CMD_OPEN, EV_CMD_CLOSE, EV_CMD_ADD_UID, EV_CMD_REMOVE_UID,
  EV_CMD_LIST_UIDS, EV_CMD_CONFIG, EV_CMD_STATUS, EV_CMD_PING,
  // Producer events
  EV_RFID_SCAN,          // i1 = granted? (0/1); uid = hex string; name = matched name if granted
  EV_PASSAGE_DETECTED,   // i1 = distance_cm at trigger, i2 = duration_ms in beam
  // Timer events (one-shot)
  EV_T_OPEN_REACHED, EV_T_PASSAGE_TIMEOUT, EV_T_WARN_GIVEUP, EV_T_CLOSE_REACHED,
};

struct event_t {
  EventSrc  src;
  EventKind kind;
  uint32_t  cmd_id;          // for ack correlation; 0 if no ack expected
  char      uid[16];         // RFID UID hex string or cmd payload
  char      name[32];        // for add_uid, or RFID matched name
  int32_t   i1, i2, i3;      // generic ints
};

struct outbound_msg_t {
  char json[UART_LINE_MAX];  // pre-serialized JSON line, NUL-terminated, no trailing \n
};
```

Fixed-size POD structs keep queues stable, avoid heap allocation in the hot path, and copy cheaply (~72 B per event).

---

## 6. Task model

Four FreeRTOS tasks. All created in `setup()` with `xTaskCreatePinnedToCore`. Core 0 holds Wi-Fi / BT stack by convention (even though Wi-Fi is disabled here, the IDF still uses core 0 for system tasks); we keep app-critical tasks on core 1.

| Task | Stack | Priority | Core | Responsibility |
| --- | --- | --- | --- | --- |
| `uart_link_task` | 4096 B | 3 | 0 | Read `Serial1` (UART1, GPIO 32 RX) byte-by-byte into a 512-B line buffer; on `\n`, parse with ArduinoJson, validate, push translated `event_t` to `event_q`. Also block on `outbound_q` (very short timeout) and `Serial1.write()` each pending JSON line to GPIO 25 TX. Single task handles both directions to serialize UART1 access. |
| `rfid_task` | 3072 B | 2 | 1 | Loop every `RFID_POLL_INTERVAL_MS`. Call `MFRC522::PICC_IsNewCardPresent()` + `PICC_ReadCardSerial()`. On hit, lookup allowlist, push `EV_RFID_SCAN`. |
| `sensor_task` | 2048 B | 2 | 1 | Loop every `SENSOR_POLL_INTERVAL_MS`. Trigger HC-SR04, read echo via `pulseIn` (max 30 ms timeout for ~5 m range). Debounce: passage event fires when distance crosses `SENSOR_TRIGGER_CM` then returns above threshold for `SENSOR_DEBOUNCE_COUNT` consecutive readings. |
| `gate_fsm_task` | 4096 B | 4 | 1 | `xQueueReceive(event_q, &e, portMAX_DELAY)`; run FSM step; call `servo_drv`/`lcd_drv`/`buzzer_drv` inline; push `evt`/`ack` to `outbound_q`. Highest priority so peripheral input is reacted to immediately. |

### 6.1 Why no separate servo / LCD / buzzer task

These are non-blocking single-call drivers:
- `servo_drv::open_now()` = `Servo::write(angle)` — returns immediately, motion happens passively while a 300 ms one-shot timer runs.
- `lcd_drv::show_name(...)` = a sequence of `LiquidCrystal_I2C::setCursor` + `print` calls totalling ~5 ms over 100 kHz I2C.
- `buzzer_drv::beep_ok()` = `digitalWrite(HIGH); vTaskDelay(80ms); digitalWrite(LOW)` — does block, but only briefly and only during user-visible feedback windows. Longer patterns (warn) use a software timer that flips the pin from a timer callback, no extra task needed.

Adding three more tasks for these would cost ~9 KB of stack and three more queues for arguments, with no responsiveness gain.

### 6.2 Queues and timers

```cpp
QueueHandle_t event_q     = xQueueCreate(EVENT_QUEUE_LEN, sizeof(event_t));
QueueHandle_t outbound_q  = xQueueCreate(OUTBOUND_QUEUE_LEN, sizeof(outbound_msg_t));

TimerHandle_t open_reached_timer    = xTimerCreate(...);   // 300 ms one-shot
TimerHandle_t passage_timeout_timer = xTimerCreate(...);   // 10 s one-shot
TimerHandle_t warn_giveup_timer     = xTimerCreate(...);   // 5 s one-shot
TimerHandle_t close_reached_timer   = xTimerCreate(...);   // 300 ms one-shot
TimerHandle_t heartbeat_timer       = xTimerCreate(...);   // 10 s auto-reload
```

Each timer's callback posts the matching `EV_T_*` event to `event_q` so the FSM sees all transitions through one input path. `heartbeat_timer` posts an outbound `evt:heartbeat` directly.

---

## 7. Module specifications

### 7.1 `uart_link`

**Public:**
```cpp
void uart_link_init();                           // Serial1.begin on GPIO 32/25, RX buffer
void uart_link_task(void* arg);                  // FreeRTOS task entry
bool uart_link_send(const outbound_msg_t& m);    // non-blocking; called by FSM
```

**RX path:** byte-by-byte read into `static char linebuf[UART_LINE_MAX]; static size_t pos;`. On `\n` (or buffer full), pass `linebuf` to `parse_line()`, then reset. `parse_line()` validates with `ArduinoJson::deserializeJson`, extracts `type`, `v`, `data`, `id`, dispatches:

| `v` | Translated event |
| --- | --- |
| `open` | `EV_CMD_OPEN`. `data.user` and `data.reason` are logged via `LOGI("cmd", "open user=%s reason=%s")` but NOT propagated through `event_t` — the FSM only needs to know "open was commanded". `cmd_id` carried for ack. |
| `close` | `EV_CMD_CLOSE` |
| `add_uid` | `EV_CMD_ADD_UID` with `data.uid → event.uid`, `data.name → event.name` |
| `remove_uid` | `EV_CMD_REMOVE_UID` with `data.uid → event.uid` |
| `list_uids` | `EV_CMD_LIST_UIDS` |
| `config` | `EV_CMD_CONFIG`. Each of `close_timeout_s`, `servo_open_deg`, `servo_close_deg` is optional. Present fields are encoded in `i1`/`i2`/`i3`; absent fields encoded as `INT32_MIN` sentinel so the handler can apply partial updates. |
| `status` | `EV_CMD_STATUS` |
| `ping` | `EV_CMD_PING` |

On parse error: drop line, push `outbound_q` with `evt:log warn "uart" "bad json: <first 40 B>"`.

**TX path:** `uart_link_task` drains `outbound_q` (timeout 10 ms) after every RX-side iteration; for each message, `Serial1.write(json); Serial1.write('\n');`. `Serial1` (ESP32 UART1) has a 128-B hardware FIFO plus the configurable RX buffer; TX is paced by the 115200 baud line (~11.5 kB/s), well above the expected <2 kB/s of app traffic. Backpressure is documented as non-issue in spec §4.6.

**Acks** for commands with `id` field are emitted by `gate_fsm` (which sees the full event including `cmd_id`) — `uart_link` only relays.

### 7.2 `rfid`

**Public:**
```cpp
void rfid_init();              // SPI.begin, MFRC522::PCD_Init
void rfid_task(void* arg);     // poll loop
```

Inside the task: every `RFID_POLL_INTERVAL_MS`, check for new card; on success, format UID as hex (`"a1b2c3d4"`), call `allowlist::lookup(uid, name_out)`, push event:
```cpp
event_t e = { .src=SRC_RFID, .kind=EV_RFID_SCAN, .cmd_id=0, .i1 = lookup_hit ? 1 : 0 };
strncpy(e.uid, uid_hex, sizeof e.uid);
if (lookup_hit) strncpy(e.name, name_out, sizeof e.name);
xQueueSend(event_q, &e, 0);
```

After reading, call `PICC_HaltA()` + `PCD_StopCrypto1()` so the same card scanned consecutively re-fires only after physical removal (avoids spam while held over reader).

### 7.3 `sensor`

**Public:**
```cpp
void sensor_init();
void sensor_task(void* arg);
```

State held inside task: `int below_count = 0; int above_count = 0; bool in_passage = false; uint32_t passage_started_ms = 0;`.

Each iteration:
1. Pulse TRIG HIGH for 10 µs, low otherwise.
2. `unsigned long us = pulseIn(PIN_SR04_ECHO, HIGH, 30000);` — 30 ms timeout (~5 m range).
3. `int cm = us / 58;` (0 if timeout).
4. If `cm > 0 && cm < SENSOR_TRIGGER_CM`: `below_count++; above_count = 0; if (!in_passage && below_count >= SENSOR_DEBOUNCE_COUNT) { in_passage = true; passage_started_ms = millis(); }`
5. Else: `above_count++; below_count = 0; if (in_passage && above_count >= SENSOR_DEBOUNCE_COUNT) { in_passage = false; push EV_PASSAGE_DETECTED with i1=cm, i2=millis()-passage_started_ms; }`

The "passage" is defined as person enters → leaves the beam, mirroring the gate-closing trigger in architecture spec §4.5.

### 7.4 `gate_fsm`

**Public:**
```cpp
void gate_fsm_init();
void gate_fsm_task(void* arg);
```

State: `static GateState state = S_IDLE;` plus runtime config (open angle, close angle, timeouts) loaded from NVS at init.

Pseudocode:
```cpp
void gate_fsm_task(void*) {
  event_t e;
  for (;;) {
    if (xQueueReceive(event_q, &e, portMAX_DELAY) != pdTRUE) continue;
    handle_event(e);
  }
}

void handle_event(const event_t& e) {
  // Commands that always work, regardless of state
  switch (e.kind) {
    case EV_CMD_PING:    ack_ok(e.cmd_id); return;
    case EV_CMD_STATUS:  ack_status(e.cmd_id); return;
    case EV_CMD_LIST_UIDS: ack_list(e.cmd_id); return;
    case EV_CMD_ADD_UID:    handle_add(e); return;
    case EV_CMD_REMOVE_UID: handle_remove(e); return;
    case EV_CMD_CONFIG:     handle_config(e); return;
    case EV_CMD_CLOSE:      force_close(e.cmd_id); return;
    default: break; // gate-affecting events handled below
  }

  switch (state) {
    case S_IDLE:        on_idle(e); break;
    case S_OPENING:     on_opening(e); break;
    case S_OPEN_WAIT:   on_open_wait(e); break;
    case S_TIMEOUT_WARN: on_timeout_warn(e); break;
    case S_CLOSING:     on_closing(e); break;
  }
}
```

Per-state transitions follow architecture spec §4.5 verbatim. Each transition emits a `evt:gate {state}` to `outbound_q` and starts/cancels the relevant timer.

**Special handling:**
- `EV_CMD_OPEN` in `S_OPEN_WAIT` → reset `passage_timeout_timer` (admin hold-open semantics).
- `EV_CMD_OPEN` in `S_OPENING`/`S_CLOSING` → ignore + ack `{ok:false, err:"busy"}`.
- `EV_RFID_SCAN` with `i1=0` (denied) in any state → `buzzer_drv::beep_err()` + `evt:rfid denied`; no FSM transition.

### 7.5 `servo_drv` / `lcd_drv` / `buzzer_drv`

Thin wrappers, no FreeRTOS objects inside.

```cpp
// servo_drv
void servo_init();
void servo_open();     // write(servo_open_deg)
void servo_close();    // write(servo_close_deg)

// lcd_drv (thread-safety: only called from gate_fsm_task → no mutex needed)
void lcd_init();
void lcd_show_idle();              // "smart_gate ready"
void lcd_show_opening();
void lcd_show_name(const char*);   // "Welcome: <name>"
void lcd_show_warn();              // "Please pass through"
void lcd_show_denied();
void lcd_show_closing();

// buzzer_drv
void buzzer_init();
void buzzer_beep_ok();             // 80 ms single beep
void buzzer_beep_err();             // 3× 60 ms beeps
void buzzer_start_warn_pattern();   // software timer flips pin every 250 ms
void buzzer_stop_warn_pattern();
```

NPN transistor on the buzzer GPIO is taken care of in hardware (architecture spec §5).

### 7.6 `allowlist`

NVS-backed, namespace `allowlist`. Each authorized UID is one Preferences key:
```cpp
Preferences prefs; prefs.begin(NVS_NS_ALLOWLIST, false);
prefs.putString(uid_hex, name);   // add
prefs.getString(uid_hex, "");      // lookup
prefs.remove(uid_hex);             // remove
```
For `list_uids` (NVS has no enumerate API for Preferences-style keys), maintain a sidecar JSON-array string in the same namespace under key `_index`:
```cpp
// _index = ["a1b2c3d4","ff00aa55",...]
```
Every mutation rewrites `_index`. Reader for `list_uids` parses `_index`, then iterates `getString(uid)` to attach names. Mutations are serialized by `gate_fsm_task` (single writer) so no NVS lock is needed beyond what Preferences provides.

**Limits:** `ALLOWLIST_MAX_ENTRIES = 100`. `add_uid` past the limit acks `{ok:false, err:"full"}`.

**Public:**
```cpp
void allowlist_init();
bool allowlist_lookup(const char* uid, char* name_out, size_t n);
int  allowlist_add(const char* uid, const char* name);    // returns new total or -1
bool allowlist_remove(const char* uid);
size_t allowlist_list(char* out_json, size_t n);          // writes JSON array
```

---

## 8. Logging & error handling

### 8.1 Log macros (`include/log.h`, created by main.cpp's first include)

```cpp
#define LOGI(tag, fmt, ...) do { ESP_LOGI(tag, fmt, ##__VA_ARGS__); emit_log("info", tag, fmt, ##__VA_ARGS__); } while (0)
#define LOGW(tag, fmt, ...) do { ESP_LOGW(tag, fmt, ##__VA_ARGS__); emit_log("warn", tag, fmt, ##__VA_ARGS__); } while (0)
#define LOGE(tag, fmt, ...) do { ESP_LOGE(tag, fmt, ##__VA_ARGS__); emit_log("err",  tag, fmt, ##__VA_ARGS__); } while (0)
```

`emit_log` formats an `evt:log {lvl, tag, msg}` message and pushes to `outbound_q`. **Rate limit:** at most 1 `evt:log` per 1 second per `(lvl, tag)` pair; overflow is dropped and counted (the next allowed log of that pair includes `dropped: N`). This prevents a stuck error from flooding the link.

### 8.2 Error paths

| Path | Handling |
| --- | --- |
| `Serial1` RX buffer overflow | Increase Arduino RX buffer with `Serial1.setRxBufferSize(1024)` at init. Should not be reachable at the spec'd throughput. |
| JSON parse error | Drop line, `LOGW("uart", "bad json: %.40s", linebuf)`. |
| `xQueueSend` returns `errQUEUE_FULL` on `event_q` | `LOGW("evt", "queue full, dropping kind=%d", e.kind)`. Queue is sized 16 which is ~16 simultaneous events — only reachable on pathological flood; loss is acceptable. |
| `xQueueSend` returns `errQUEUE_FULL` on `outbound_q` | Drop with `Serial.println("{\"type\":\"evt\",\"v\":\"log\",\"data\":{\"lvl\":\"warn\",\"tag\":\"tx\",\"msg\":\"outbound full\"}}");` (bypass queue, best-effort). |
| `Preferences::putString` returns 0 | Ack `{ok:false, err:"nvs_write"}`, `LOGE("nvs", ...)`. |
| RC522 read returns garbage repeatedly | `LOGW("rfid", "consecutive read failures: %d", n)` every 1 s; do not crash. |
| HC-SR04 returns 0 (timeout) for >30 s straight | `LOGW("sensor", "no echo for 30s")` — could be sensor disconnect. Do not change FSM behavior; the FSM treats absence of passage as "still waiting". |

### 8.3 Watchdog

ESP32 Task Watchdog Timer (TWDT):
- Enable at `setup()` with 8 s timeout, panic on expiry.
- Subscribe only `gate_fsm_task` (the FSM is the responsiveness contract; if it stalls, reboot).
- `gate_fsm_task` calls `esp_task_wdt_reset()` on every event loop iteration.
- `uart_link_task`, `rfid_task`, `sensor_task` are not subscribed because they intentionally block on I/O for tens of milliseconds; a TWDT trip there would be a false positive.

Hardware brownout detector uses the default ESP32 cutoff (~2.43 V); sufficient given the 5 V → 3.3 V LDO + servo spike mitigation in architecture spec §2.2.

---

## 9. Boot sequence (`main.cpp::setup`)

```text
1. Serial.begin(UART_BAUD) [UART0 debug]; Serial1.begin(UART_BAUD, SERIAL_8N1, PIN_PI_UART_RX, PIN_PI_UART_TX) [UART1 Pi link]; Serial1.setRxBufferSize(1024)
2. NVS init (nvs_flash_init); allowlist_init(); load runtime config from NVS_NS_CONFIG
3. uart_link_init()
4. rfid_init(); sensor_init(); servo_init(); lcd_init(); buzzer_init()
5. lcd_show_idle()
6. Create event_q, outbound_q
7. Create timers (open_reached, passage_timeout, warn_giveup, close_reached, heartbeat)
8. xTimerStart(heartbeat_timer, 0)
9. xTaskCreatePinnedToCore for uart_link, rfid, sensor, gate_fsm
10. Enable TWDT (8 s), subscribe gate_fsm_task
11. Emit evt:boot {fw, free_heap, reset_reason}
12. setup() returns; loop() body is empty (vTaskDelete(NULL) would also work but unnecessary)
```

`reset_reason` is read with `esp_reset_reason()` and mapped to a string (`"power_on"`, `"sw_reset"`, `"panic"`, `"watchdog"`, `"brownout"`, `"other"`).

---

## 10. Testing strategy (manual + serial logs)

Per design decision (recorded in brainstorming): no Unity tests, no hardware-in-the-loop harness. Verification is by flashing the board and observing `pio device monitor` (or equivalent on the Pi) for the expected JSON Lines. The scenarios below are reproduced verbatim in the README under "Acceptance tests" so a tester can walk through them.

| # | Scenario | Expected serial output |
| --- | --- | --- |
| 1 | Power on board | One line `{"type":"evt","v":"boot","data":{"fw":"1.0.0","free_heap":N,"reset_reason":"power_on"}}` within 500 ms |
| 2 | Send `{"id":1,"type":"cmd","v":"ping"}\n` from Pi | One line `{"type":"ack","id":1,"v":"ping","data":{"ok":true}}` within 100 ms |
| 3 | Scan whitelisted card | `evt:rfid granted` with matching `name`; `evt:gate opening` → `evt:gate open` after 300 ms; LCD shows `"Welcome: <name>"`; servo physically opens |
| 4 | Pass hand through HC-SR04 beam | `evt:person_passed` with reasonable `distance_cm` and `ms`; then `evt:gate closing` → `evt:gate closed` |
| 5 | Scan non-whitelisted card | `evt:rfid denied`; buzzer emits triple-beep; no gate motion |
| 6 | Send `cmd:open` then do nothing | `evt:gate opening` → `evt:gate open`; after 10 s, `evt:gate timeout_warn` and buzzer warn pattern starts; after 5 s, `evt:gate closing` → `evt:gate closed` |
| 7 | `add_uid` → `list_uids` → reboot → `list_uids` | Second `list_uids` after reboot still contains the added UID |
| 8 | `remove_uid` for unknown UID | `ack` with `{"ok":false,"err":"not_found"}` |
| 9 | Send `cmd:config {"close_timeout_s":3}` then `cmd:open` and idle | Timeout warning fires at 3 s instead of 10 s |
| 10 | Disconnect Pi USB, scan whitelisted card | RFID flow still works end-to-end (boards keeps operating standalone) |
| 11 | Send malformed JSON | `evt:log warn` with `tag:"uart"`; next valid message still processed normally |
| 12 | Hold whitelisted card on reader continuously | `evt:rfid granted` fires once; subsequent identical events suppressed until card removed |

Pass/fail is recorded by the operator. Failed scenarios become bug tickets.

---

## 11. Build, flash, monitor

Pi-side (the firmware repo lives at `/home/nguyenvd/workspace/smart_gate/firmware`):

```bash
# Build
pio run

# Flash (requires Pi pyserial app to release /dev/ttyUSB0)
pio run -t upload

# Open serial monitor at 115200 baud
pio device monitor
```

CI is **out of scope** for this prototype. A local `pio check` (cppcheck-backed) lint may be added if it proves cheap to wire up.

---

## 12. Risks & open items

1. **Library version drift.** Pinning `^7.0` / `^1.4` / `^3.0` / `^1.1` means PlatformIO will pull the latest compatible release at first build. If a future minor breaks something, lock to exact versions in `platformio.ini`.
2. **`evt:log` flood under brownout.** A brownout-recovering board can re-init in a loop. Rate limit in §8.1 mitigates but does not eliminate the symptom; ultimate protection is the brownout detector itself.
3. **`pulseIn` blocking 30 ms in `sensor_task`** holds core 1 for that interval. Acceptable because no other task on core 1 is latency-critical between sensor polls (RFID polls more slowly at 50 ms intervals, FSM is idle waiting for events).
4. **MFRC522 SPI conflict with future SD card / additional SPI device.** Not in scope, but the carrier PCB may add SD at some point. CS pin selection (GPIO 5) is already strapping-conscious and shareable.
5. **LCD I2C pull-up cut (architecture spec §9.1).** Firmware assumes the hardware fix is done; if pull-ups are uncut, LCD writes may appear flaky. The README must call this out.

---

## 13. Out of scope

- OTA update mechanism. Re-flash via `pio run -t upload` is the supported update path (matches architecture spec §8).
- Wi-Fi / MQTT. Architecture decided GPIO UART1 (3-wire link) is the only runtime link; USB-CDC remains for flashing + monitor only.
- Encryption / signed firmware. Prototype.
- Power-failure-safe NVS writes beyond what Preferences provides by default.
- Mocking/Unity tests — explicitly chosen out (manual + serial logs).
- Pi-side code, KiCad schematics, FreeCAD models — belong to other sessions.

---

*End of firmware design spec.*
