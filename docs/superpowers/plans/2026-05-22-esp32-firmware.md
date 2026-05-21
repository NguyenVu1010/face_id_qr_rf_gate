# ESP32 Firmware Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the ESP32 firmware described in `docs/superpowers/specs/2026-05-22-esp32-firmware-design.md`: a four-task FreeRTOS application that drives RFID auth, servo, LCD, HC-SR04 passage sensor, and buzzer; talks JSON Lines over USB-CDC to a Raspberry Pi 5.

**Architecture:** Arduino-ESP32 via PlatformIO. Four FreeRTOS tasks (`uart_link`, `rfid`, `sensor`, `gate_fsm`) pinned to specific cores; events flow through one `event_q` into the FSM; outbound JSON flows through one `outbound_q` back to UART. NVS Preferences store the RFID allowlist. Inline driver wrappers for servo/LCD/buzzer (no separate tasks).

**Tech Stack:** PlatformIO (`espressif32@^6.0`), Arduino-ESP32, ArduinoJson 7, MFRC522 1.4, ESP32Servo 3, LiquidCrystal_I2C 1.1.

**Verification model:** This is embedded firmware; no automated unit tests (per spec §10). The "test passes" gate for each task is **`pio run` compiles clean with zero warnings**. Manual hardware acceptance is deferred to a final task that walks the 12 scenarios from spec §10.

---

## File Structure

All paths are relative to `/home/nguyenvd/workspace/smart_gate/`:

| File | Created in task | Responsibility |
| --- | --- | --- |
| `firmware/platformio.ini` | 0 | PlatformIO env + deps |
| `firmware/.gitignore` | 0 | Ignore `.pio/`, build artifacts |
| `firmware/README.md` | 0 (stub) → 11 (filled) | Pin map, build/flash, acceptance scenarios |
| `firmware/include/config.h` | 1 | Pin defs, timing constants, sizes |
| `firmware/include/events.h` | 1 | `event_t`, `outbound_msg_t`, enums |
| `firmware/include/version.h` | 1 | `FW_VERSION` |
| `firmware/include/log.h` | 1 | `LOGI/LOGW/LOGE` macros |
| `firmware/src/main.cpp` | 0 (stub) → 9 (filled) | `setup()` boot sequence + task creation |
| `firmware/src/allowlist.h` | 2 | UID/name store interface |
| `firmware/src/allowlist.cpp` | 2 | NVS Preferences-backed implementation |
| `firmware/src/servo_drv.h` | 3 | Servo open/close wrappers |
| `firmware/src/servo_drv.cpp` | 3 | LEDC PWM via ESP32Servo |
| `firmware/src/lcd_drv.h` | 3 | LCD line helpers |
| `firmware/src/lcd_drv.cpp` | 3 | LiquidCrystal_I2C calls |
| `firmware/src/buzzer_drv.h` | 3 | Beep helpers |
| `firmware/src/buzzer_drv.cpp` | 3 | GPIO + software-timer pattern |
| `firmware/src/log_emit.h` | 4 | `emit_log()` declaration |
| `firmware/src/log_emit.cpp` | 4 | Rate-limited JSON log line builder |
| `firmware/src/uart_link.h` | 5 | Public API |
| `firmware/src/uart_link.cpp` | 5 | RX line buffer + JSON parse + TX drain |
| `firmware/src/rfid.h` | 6 | Public API |
| `firmware/src/rfid.cpp` | 6 | MFRC522 polling task |
| `firmware/src/sensor.h` | 7 | Public API |
| `firmware/src/sensor.cpp` | 7 | HC-SR04 polling + debounce |
| `firmware/src/gate_fsm.h` | 8 | Public API + GateState enum |
| `firmware/src/gate_fsm.cpp` | 8 | State machine, timer callbacks, handlers |

---

## Task 0: Bootstrap PlatformIO project skeleton

**Files:**
- Create: `firmware/platformio.ini`
- Create: `firmware/.gitignore`
- Create: `firmware/README.md` (stub)
- Create: `firmware/src/main.cpp` (stub)

- [ ] **Step 1: Create the `firmware/` directory and `platformio.ini`**

Create `firmware/platformio.ini`:

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
    -Wall
    -Wextra
lib_deps =
    bblanchon/ArduinoJson@^7.0
    miguelbalboa/MFRC522@^1.4
    madhephaestus/ESP32Servo@^3.0
    marcoschwartz/LiquidCrystal_I2C@^1.1
```

- [ ] **Step 2: Create `firmware/.gitignore`**

```gitignore
.pio/
.pioenvs/
.piolibdeps/
.vscode/
.clang_complete
.gcc-flags.json
build/
*.o
*.a
*.elf
*.bin
*.hex
```

- [ ] **Step 3: Create `firmware/README.md` stub**

```markdown
# smart_gate ESP32 firmware

See `../docs/superpowers/specs/2026-05-22-esp32-firmware-design.md` for the design.

## Build

```bash
pio run
```

## Flash

```bash
# Pi pyserial app must release /dev/ttyUSB0 first.
pio run -t upload
```

## Monitor

```bash
pio device monitor
```

Pin map and acceptance test scenarios are added in Task 11.
```

- [ ] **Step 4: Create `firmware/src/main.cpp` stub**

```cpp
#include <Arduino.h>

void setup() {
  Serial.begin(115200);
  delay(50);
  Serial.println("smart_gate firmware boot (stub)");
}

void loop() {
  delay(1000);
}
```

- [ ] **Step 5: Build to verify toolchain pulls deps and stub compiles**

Run: `cd firmware && pio run`
Expected: First run downloads platform + libraries (one-time, may take 2–5 minutes), then prints `Building in release mode` and finally `========== [SUCCESS] ...`. The build artifact `.pio/build/esp32dev/firmware.elf` exists.

- [ ] **Step 6: Commit**

```bash
cd /home/nguyenvd/workspace/smart_gate
git add firmware/platformio.ini firmware/.gitignore firmware/README.md firmware/src/main.cpp
git commit -m "feat(firmware): bootstrap PlatformIO project skeleton"
```

---

## Task 1: Shared headers (config, events, version, log)

**Files:**
- Create: `firmware/include/version.h`
- Create: `firmware/include/config.h`
- Create: `firmware/include/events.h`
- Create: `firmware/include/log.h`

- [ ] **Step 1: Create `firmware/include/version.h`**

```cpp
#pragma once

#ifndef FW_VERSION
#define FW_VERSION "1.0.0"
#endif
```

- [ ] **Step 2: Create `firmware/include/config.h`**

```cpp
#pragma once

// === Pin assignments (mirror architecture spec §5) ===
#define PIN_LED_STATUS   2
#define PIN_RC522_CS     5
#define PIN_RC522_SCK    18
#define PIN_RC522_MISO   19
#define PIN_RC522_MOSI   23
#define PIN_RC522_RST    17
#define PIN_RC522_IRQ    16
#define PIN_LCD_SDA      21
#define PIN_LCD_SCL      22
#define PIN_SR04_TRIG    27
#define PIN_SR04_ECHO    26
#define PIN_SERVO        13
#define PIN_BUZZER       14

// === Timings (ms) ===
#define DEFAULT_OPEN_REACHED_MS    300
#define DEFAULT_CLOSE_REACHED_MS   300
#define DEFAULT_PASSAGE_TIMEOUT_MS 10000
#define DEFAULT_WARN_GIVEUP_MS     5000
#define HEARTBEAT_INTERVAL_MS      10000
#define RFID_POLL_INTERVAL_MS      50
#define SENSOR_POLL_INTERVAL_MS    50
#define SENSOR_DEBOUNCE_COUNT      3
#define SENSOR_TRIGGER_CM          25

// === Servo angles ===
#define DEFAULT_SERVO_OPEN_DEG     100
#define DEFAULT_SERVO_CLOSE_DEG    10

// === LCD ===
#define LCD_I2C_ADDR              0x27
#define LCD_COLS                  20
#define LCD_ROWS                  4

// === NVS ===
#define NVS_NS_ALLOWLIST          "allowlist"
#define NVS_NS_CONFIG             "config"
#define NVS_INDEX_KEY             "_index"
#define ALLOWLIST_MAX_ENTRIES     100

// === UART / JSON ===
#define UART_BAUD                 115200
#define UART_LINE_MAX             512
#define JSON_DOC_CAPACITY         768
#define EVENT_QUEUE_LEN           16
#define OUTBOUND_QUEUE_LEN        16
```

- [ ] **Step 3: Create `firmware/include/events.h`**

```cpp
#pragma once
#include <stdint.h>
#include "config.h"

enum EventSrc : uint8_t { SRC_UART, SRC_RFID, SRC_SENSOR, SRC_TIMER };

enum EventKind : uint8_t {
  // Commands from Pi
  EV_CMD_OPEN, EV_CMD_CLOSE, EV_CMD_ADD_UID, EV_CMD_REMOVE_UID,
  EV_CMD_LIST_UIDS, EV_CMD_CONFIG, EV_CMD_STATUS, EV_CMD_PING,
  // Producer events
  EV_RFID_SCAN,          // i1 = granted? (0/1); uid set; name set if granted
  EV_PASSAGE_DETECTED,   // i1 = distance_cm at trigger, i2 = duration_ms in beam
  // Timer events (one-shot)
  EV_T_OPEN_REACHED, EV_T_PASSAGE_TIMEOUT, EV_T_WARN_GIVEUP, EV_T_CLOSE_REACHED,
};

struct event_t {
  EventSrc  src;
  EventKind kind;
  uint32_t  cmd_id;          // ack correlation; 0 if N/A
  char      uid[16];         // RFID UID hex or cmd payload
  char      name[32];        // add_uid name or RFID matched name
  int32_t   i1, i2, i3;      // generic ints; INT32_MIN sentinel = "unset" for cmd_config
};

struct outbound_msg_t {
  char json[UART_LINE_MAX];  // pre-serialized JSON line, NUL-terminated, no trailing newline
};
```

- [ ] **Step 4: Create `firmware/include/log.h`**

```cpp
#pragma once
#include <esp_log.h>
#include "../src/log_emit.h"  // emit_log declared in src/

#define LOGI(tag, fmt, ...) do { ESP_LOGI(tag, fmt, ##__VA_ARGS__); emit_log("info", tag, fmt, ##__VA_ARGS__); } while (0)
#define LOGW(tag, fmt, ...) do { ESP_LOGW(tag, fmt, ##__VA_ARGS__); emit_log("warn", tag, fmt, ##__VA_ARGS__); } while (0)
#define LOGE(tag, fmt, ...) do { ESP_LOGE(tag, fmt, ##__VA_ARGS__); emit_log("err",  tag, fmt, ##__VA_ARGS__); } while (0)
```

Note: `log_emit.h` does not exist yet — `log.h` will fail to compile until Task 4. That is intentional; we land Task 4 before any module that uses `LOGx`.

- [ ] **Step 5: Build to verify config.h, events.h, version.h compile standalone**

Add a temporary `#include "config.h"` and `#include "events.h"` to `firmware/src/main.cpp` (above the existing `#include <Arduino.h>`).

Run: `cd firmware && pio run`
Expected: SUCCESS. No warnings.

Then remove the temporary includes from `main.cpp` (they will be reintroduced properly in Task 9). `main.cpp` reverts to the Task-0 stub.

- [ ] **Step 6: Commit**

```bash
cd /home/nguyenvd/workspace/smart_gate
git add firmware/include/
git commit -m "feat(firmware): add shared headers (config, events, version, log)"
```

---

## Task 2: `allowlist` module (NVS-backed UID store)

**Files:**
- Create: `firmware/src/allowlist.h`
- Create: `firmware/src/allowlist.cpp`

- [ ] **Step 1: Create `firmware/src/allowlist.h`**

```cpp
#pragma once
#include <stddef.h>

void   allowlist_init();
bool   allowlist_lookup(const char* uid_hex, char* name_out, size_t name_out_n);
int    allowlist_add(const char* uid_hex, const char* name);   // returns new total, or -1 if full / -2 on NVS error
bool   allowlist_remove(const char* uid_hex);                  // false if not found
size_t allowlist_list_json(char* out_json, size_t out_json_n); // writes [{"uid":"...","name":"..."},...]; returns bytes written or 0 on overflow
size_t allowlist_count();
```

- [ ] **Step 2: Create `firmware/src/allowlist.cpp`**

```cpp
#include "allowlist.h"
#include "../include/config.h"
#include <Preferences.h>
#include <ArduinoJson.h>
#include <string.h>

static Preferences prefs;

// _index is a JSON array of UID hex strings, e.g. ["a1b2c3d4","ff00aa55"]
static bool index_load(JsonDocument& doc) {
  String s = prefs.getString(NVS_INDEX_KEY, "[]");
  DeserializationError e = deserializeJson(doc, s);
  return !e;
}

static bool index_save(JsonDocument& doc) {
  String s;
  serializeJson(doc, s);
  return prefs.putString(NVS_INDEX_KEY, s) > 0;
}

void allowlist_init() {
  prefs.begin(NVS_NS_ALLOWLIST, /*readOnly=*/false);
  // Ensure index exists
  if (!prefs.isKey(NVS_INDEX_KEY)) {
    prefs.putString(NVS_INDEX_KEY, "[]");
  }
}

bool allowlist_lookup(const char* uid_hex, char* name_out, size_t name_out_n) {
  if (!prefs.isKey(uid_hex)) return false;
  String n = prefs.getString(uid_hex, "");
  if (n.length() == 0) return false;
  strncpy(name_out, n.c_str(), name_out_n - 1);
  name_out[name_out_n - 1] = '\0';
  return true;
}

int allowlist_add(const char* uid_hex, const char* name) {
  JsonDocument doc;
  if (!index_load(doc)) return -2;
  JsonArray arr = doc.as<JsonArray>();
  // Skip if already present
  bool already = false;
  for (JsonVariant v : arr) {
    if (strcmp(v.as<const char*>(), uid_hex) == 0) { already = true; break; }
  }
  if (!already) {
    if (arr.size() >= ALLOWLIST_MAX_ENTRIES) return -1;
    arr.add(uid_hex);
    if (!index_save(doc)) return -2;
  }
  if (prefs.putString(uid_hex, name) == 0) return -2;
  return (int)arr.size();
}

bool allowlist_remove(const char* uid_hex) {
  if (!prefs.isKey(uid_hex)) return false;
  JsonDocument doc;
  if (!index_load(doc)) return false;
  JsonArray arr = doc.as<JsonArray>();
  // Rebuild without the target UID
  JsonDocument out;
  JsonArray out_arr = out.to<JsonArray>();
  for (JsonVariant v : arr) {
    if (strcmp(v.as<const char*>(), uid_hex) != 0) out_arr.add(v.as<const char*>());
  }
  index_save(out);
  prefs.remove(uid_hex);
  return true;
}

size_t allowlist_list_json(char* out_json, size_t out_json_n) {
  JsonDocument idx;
  if (!index_load(idx)) return 0;
  JsonDocument out;
  JsonArray out_arr = out.to<JsonArray>();
  for (JsonVariant v : idx.as<JsonArray>()) {
    const char* uid = v.as<const char*>();
    String n = prefs.getString(uid, "");
    JsonObject o = out_arr.add<JsonObject>();
    o["uid"] = uid;
    o["name"] = n.c_str();
  }
  size_t w = serializeJson(out, out_json, out_json_n);
  if (w == 0 || w >= out_json_n) return 0;
  return w;
}

size_t allowlist_count() {
  JsonDocument doc;
  if (!index_load(doc)) return 0;
  return doc.as<JsonArray>().size();
}
```

- [ ] **Step 3: Build to verify allowlist.cpp compiles**

Add to `firmware/src/main.cpp` setup() (temporarily, will be removed in Task 9):

```cpp
#include "allowlist.h"
// ... inside setup():
allowlist_init();
char name[32];
(void)allowlist_lookup("test", name, sizeof name);
```

Run: `cd firmware && pio run`
Expected: SUCCESS.

Remove the temporary lines from `main.cpp` after verifying. Revert to Task-0 stub.

- [ ] **Step 4: Commit**

```bash
cd /home/nguyenvd/workspace/smart_gate
git add firmware/src/allowlist.h firmware/src/allowlist.cpp
git commit -m "feat(firmware): add NVS-backed RFID allowlist module"
```

---

## Task 3: Inline drivers (`servo_drv`, `lcd_drv`, `buzzer_drv`)

**Files:**
- Create: `firmware/src/servo_drv.h`
- Create: `firmware/src/servo_drv.cpp`
- Create: `firmware/src/lcd_drv.h`
- Create: `firmware/src/lcd_drv.cpp`
- Create: `firmware/src/buzzer_drv.h`
- Create: `firmware/src/buzzer_drv.cpp`

- [ ] **Step 1: Create `firmware/src/servo_drv.h`**

```cpp
#pragma once

void servo_init();
void servo_set_angles(int open_deg, int close_deg);  // runtime override; persisted by caller
void servo_open();
void servo_close();
int  servo_open_deg();
int  servo_close_deg();
```

- [ ] **Step 2: Create `firmware/src/servo_drv.cpp`**

```cpp
#include "servo_drv.h"
#include "../include/config.h"
#include <ESP32Servo.h>

static Servo s_servo;
static int s_open_deg  = DEFAULT_SERVO_OPEN_DEG;
static int s_close_deg = DEFAULT_SERVO_CLOSE_DEG;

void servo_init() {
  s_servo.setPeriodHertz(50);
  s_servo.attach(PIN_SERVO, 500, 2400);  // typical SG90 pulse range µs
  s_servo.write(s_close_deg);
}

void servo_set_angles(int open_deg, int close_deg) {
  if (open_deg  >= 0 && open_deg  <= 180) s_open_deg  = open_deg;
  if (close_deg >= 0 && close_deg <= 180) s_close_deg = close_deg;
}

void servo_open()  { s_servo.write(s_open_deg); }
void servo_close() { s_servo.write(s_close_deg); }
int  servo_open_deg()  { return s_open_deg; }
int  servo_close_deg() { return s_close_deg; }
```

- [ ] **Step 3: Create `firmware/src/lcd_drv.h`**

```cpp
#pragma once

void lcd_init();
void lcd_show_idle();
void lcd_show_opening();
void lcd_show_name(const char* name);
void lcd_show_warn();
void lcd_show_denied();
void lcd_show_closing();
```

- [ ] **Step 4: Create `firmware/src/lcd_drv.cpp`**

```cpp
#include "lcd_drv.h"
#include "../include/config.h"
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

static LiquidCrystal_I2C s_lcd(LCD_I2C_ADDR, LCD_COLS, LCD_ROWS);

static void write_row(int row, const char* text) {
  s_lcd.setCursor(0, row);
  // Pad/truncate to LCD_COLS
  char buf[LCD_COLS + 1];
  size_t n = strlen(text);
  for (int i = 0; i < LCD_COLS; ++i) {
    buf[i] = (size_t)i < n ? text[i] : ' ';
  }
  buf[LCD_COLS] = '\0';
  s_lcd.print(buf);
}

void lcd_init() {
  Wire.begin(PIN_LCD_SDA, PIN_LCD_SCL);
  s_lcd.init();
  s_lcd.backlight();
  lcd_show_idle();
}

void lcd_show_idle() {
  s_lcd.clear();
  write_row(0, "smart_gate ready");
  write_row(1, "Tap RFID or wait");
  write_row(2, "for face auth");
  write_row(3, "");
}

void lcd_show_opening() {
  s_lcd.clear();
  write_row(0, "Opening gate...");
}

void lcd_show_name(const char* name) {
  s_lcd.clear();
  write_row(0, "Welcome:");
  write_row(1, name);
}

void lcd_show_warn() {
  s_lcd.clear();
  write_row(0, "Please pass thru");
  write_row(1, "or gate closes");
}

void lcd_show_denied() {
  s_lcd.clear();
  write_row(0, "Access denied");
}

void lcd_show_closing() {
  s_lcd.clear();
  write_row(0, "Closing...");
}
```

- [ ] **Step 5: Create `firmware/src/buzzer_drv.h`**

```cpp
#pragma once

void buzzer_init();
void buzzer_beep_ok();              // single 80ms beep
void buzzer_beep_err();             // 3× 60ms beeps
void buzzer_start_warn_pattern();   // toggling pattern via software timer
void buzzer_stop_warn_pattern();
```

- [ ] **Step 6: Create `firmware/src/buzzer_drv.cpp`**

```cpp
#include "buzzer_drv.h"
#include "../include/config.h"
#include <Arduino.h>
#include "freertos/FreeRTOS.h"
#include "freertos/timers.h"

static TimerHandle_t s_warn_timer = nullptr;
static volatile bool s_warn_state = false;

static void warn_timer_cb(TimerHandle_t) {
  s_warn_state = !s_warn_state;
  digitalWrite(PIN_BUZZER, s_warn_state ? HIGH : LOW);
}

void buzzer_init() {
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);
  s_warn_timer = xTimerCreate("buzzerWarn", pdMS_TO_TICKS(250), pdTRUE, nullptr, warn_timer_cb);
}

void buzzer_beep_ok() {
  digitalWrite(PIN_BUZZER, HIGH);
  vTaskDelay(pdMS_TO_TICKS(80));
  digitalWrite(PIN_BUZZER, LOW);
}

void buzzer_beep_err() {
  for (int i = 0; i < 3; ++i) {
    digitalWrite(PIN_BUZZER, HIGH);
    vTaskDelay(pdMS_TO_TICKS(60));
    digitalWrite(PIN_BUZZER, LOW);
    vTaskDelay(pdMS_TO_TICKS(60));
  }
}

void buzzer_start_warn_pattern() {
  s_warn_state = false;
  if (s_warn_timer) xTimerStart(s_warn_timer, 0);
}

void buzzer_stop_warn_pattern() {
  if (s_warn_timer) xTimerStop(s_warn_timer, 0);
  digitalWrite(PIN_BUZZER, LOW);
}
```

- [ ] **Step 7: Build**

Run: `cd firmware && pio run`
Expected: SUCCESS. (At this point, the new drivers are not yet referenced from main, but they must still compile cleanly as standalone TUs because PlatformIO compiles every .cpp in `src/`.)

- [ ] **Step 8: Commit**

```bash
cd /home/nguyenvd/workspace/smart_gate
git add firmware/src/servo_drv.* firmware/src/lcd_drv.* firmware/src/buzzer_drv.*
git commit -m "feat(firmware): add inline drivers (servo, LCD, buzzer)"
```

---

## Task 4: `log_emit` module (rate-limited `evt:log` emitter)

**Files:**
- Create: `firmware/src/log_emit.h`
- Create: `firmware/src/log_emit.cpp`

- [ ] **Step 1: Create `firmware/src/log_emit.h`**

```cpp
#pragma once
#include <stdint.h>

// Forward declaration: defined in uart_link.cpp; safe to call before uart_link_init returns
// (early calls are buffered into outbound_q only if it exists; otherwise dropped silently).
struct outbound_msg_t;
extern "C" void outbound_post(const struct outbound_msg_t* m);  // implemented in uart_link.cpp

void emit_log(const char* lvl, const char* tag, const char* fmt, ...);
```

- [ ] **Step 2: Create `firmware/src/log_emit.cpp`**

```cpp
#include "log_emit.h"
#include "../include/events.h"
#include "../include/config.h"
#include <ArduinoJson.h>
#include <Arduino.h>
#include <stdarg.h>
#include <string.h>

// Rate limit table: one slot per (lvl,tag) pair. Linear scan is fine because we cap at 16 distinct pairs.
#define RL_SLOTS 16
struct rl_slot_t {
  char lvl[8];
  char tag[16];
  uint32_t last_ms;
  uint32_t dropped;
  bool used;
};
static rl_slot_t s_rl[RL_SLOTS];

// Returns true if this log should be allowed; sets *dropped_out if there's a pending drop count to flush.
static bool rl_check(const char* lvl, const char* tag, uint32_t* dropped_out) {
  uint32_t now = millis();
  int free_idx = -1;
  for (int i = 0; i < RL_SLOTS; ++i) {
    if (!s_rl[i].used) { if (free_idx < 0) free_idx = i; continue; }
    if (strncmp(s_rl[i].lvl, lvl, sizeof s_rl[i].lvl) == 0 &&
        strncmp(s_rl[i].tag, tag, sizeof s_rl[i].tag) == 0) {
      if (now - s_rl[i].last_ms >= 1000) {
        *dropped_out = s_rl[i].dropped;
        s_rl[i].dropped = 0;
        s_rl[i].last_ms = now;
        return true;
      } else {
        s_rl[i].dropped++;
        return false;
      }
    }
  }
  if (free_idx >= 0) {
    s_rl[free_idx].used = true;
    strncpy(s_rl[free_idx].lvl, lvl, sizeof s_rl[free_idx].lvl - 1);
    s_rl[free_idx].lvl[sizeof s_rl[free_idx].lvl - 1] = '\0';
    strncpy(s_rl[free_idx].tag, tag, sizeof s_rl[free_idx].tag - 1);
    s_rl[free_idx].tag[sizeof s_rl[free_idx].tag - 1] = '\0';
    s_rl[free_idx].last_ms = now;
    s_rl[free_idx].dropped = 0;
    *dropped_out = 0;
    return true;
  }
  // Table full: allow but no rate limiting for this pair.
  *dropped_out = 0;
  return true;
}

void emit_log(const char* lvl, const char* tag, const char* fmt, ...) {
  uint32_t dropped = 0;
  if (!rl_check(lvl, tag, &dropped)) return;

  char msg[256];
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(msg, sizeof msg, fmt, ap);
  va_end(ap);

  JsonDocument doc;
  doc["type"] = "evt";
  doc["v"]    = "log";
  JsonObject data = doc["data"].to<JsonObject>();
  data["lvl"] = lvl;
  data["tag"] = tag;
  data["msg"] = msg;
  if (dropped > 0) data["dropped"] = dropped;

  outbound_msg_t out;
  size_t w = serializeJson(doc, out.json, sizeof out.json);
  if (w == 0 || w >= sizeof out.json) return;
  outbound_post(&out);
}
```

- [ ] **Step 3: Build (will fail with undefined `outbound_post` — that's expected, but the compile of `log_emit.cpp` itself should succeed)**

Run: `cd firmware && pio run`
Expected: Compilation of `log_emit.cpp` succeeds; **link will fail** with `undefined reference to outbound_post`. That's intentional — `outbound_post` is implemented in Task 5.

Workaround for this task only: add a temporary stub at the bottom of `firmware/src/main.cpp`:

```cpp
extern "C" void outbound_post(const struct outbound_msg_t*) { /* stub, removed in Task 5 */ }
```

Re-run: `cd firmware && pio run`
Expected: SUCCESS.

- [ ] **Step 4: Commit**

```bash
cd /home/nguyenvd/workspace/smart_gate
git add firmware/src/log_emit.h firmware/src/log_emit.cpp firmware/src/main.cpp
git commit -m "feat(firmware): add rate-limited evt:log emitter"
```

---

## Task 5: `uart_link` module (JSON Lines RX/TX)

**Files:**
- Create: `firmware/src/uart_link.h`
- Create: `firmware/src/uart_link.cpp`
- Modify: `firmware/src/main.cpp` (remove `outbound_post` stub introduced in Task 4)

- [ ] **Step 1: Create `firmware/src/uart_link.h`**

```cpp
#pragma once
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "../include/events.h"

// Globals owned by main.cpp, declared here for module access:
extern QueueHandle_t g_event_q;
extern QueueHandle_t g_outbound_q;

void uart_link_init();
void uart_link_task(void* arg);

// Helper used by FSM / log_emit to enqueue an outbound JSON Line.
// Returns true if queued, false if queue full (caller decides whether to drop or fallback).
bool outbound_send(const outbound_msg_t& m);
```

- [ ] **Step 2: Create `firmware/src/uart_link.cpp`**

```cpp
#include "uart_link.h"
#include "../include/log.h"
#include "../include/config.h"
#include <Arduino.h>
#include <ArduinoJson.h>
#include <string.h>

// === outbound_post: C-linkage shim for log_emit (forward-declared there) ===
extern "C" void outbound_post(const outbound_msg_t* m) {
  if (!g_outbound_q || !m) return;
  // Best-effort: drop if full (fallback handled at the caller; logs are advisory anyway).
  xQueueSend(g_outbound_q, m, 0);
}

bool outbound_send(const outbound_msg_t& m) {
  if (!g_outbound_q) return false;
  return xQueueSend(g_outbound_q, &m, 0) == pdTRUE;
}

// === RX line buffer + parser ===

static char s_linebuf[UART_LINE_MAX];
static size_t s_pos = 0;

static void translate_and_enqueue(JsonDocument& doc) {
  const char* type = doc["type"] | "";
  if (strcmp(type, "cmd") != 0) {
    LOGW("uart", "ignored non-cmd type='%s'", type);
    return;
  }
  const char* v = doc["v"] | "";
  uint32_t cmd_id = (uint32_t)(doc["id"] | 0);

  event_t e = {};
  e.src = SRC_UART;
  e.cmd_id = cmd_id;

  if      (strcmp(v, "open") == 0) {
    e.kind = EV_CMD_OPEN;
    const char* user   = doc["data"]["user"]   | "";
    const char* reason = doc["data"]["reason"] | "";
    LOGI("cmd", "open user=%s reason=%s", user, reason);
  }
  else if (strcmp(v, "close") == 0)    e.kind = EV_CMD_CLOSE;
  else if (strcmp(v, "add_uid") == 0) {
    e.kind = EV_CMD_ADD_UID;
    const char* uid = doc["data"]["uid"]  | "";
    const char* nm  = doc["data"]["name"] | "";
    strncpy(e.uid,  uid, sizeof e.uid - 1);
    strncpy(e.name, nm,  sizeof e.name - 1);
  }
  else if (strcmp(v, "remove_uid") == 0) {
    e.kind = EV_CMD_REMOVE_UID;
    const char* uid = doc["data"]["uid"] | "";
    strncpy(e.uid, uid, sizeof e.uid - 1);
  }
  else if (strcmp(v, "list_uids") == 0) e.kind = EV_CMD_LIST_UIDS;
  else if (strcmp(v, "config") == 0) {
    e.kind = EV_CMD_CONFIG;
    e.i1 = doc["data"]["close_timeout_s"].is<int>()  ? (int)doc["data"]["close_timeout_s"]  : INT32_MIN;
    e.i2 = doc["data"]["servo_open_deg"].is<int>()   ? (int)doc["data"]["servo_open_deg"]   : INT32_MIN;
    e.i3 = doc["data"]["servo_close_deg"].is<int>()  ? (int)doc["data"]["servo_close_deg"]  : INT32_MIN;
  }
  else if (strcmp(v, "status") == 0)   e.kind = EV_CMD_STATUS;
  else if (strcmp(v, "ping") == 0)     e.kind = EV_CMD_PING;
  else {
    LOGW("uart", "unknown verb '%s'", v);
    return;
  }

  if (xQueueSend(g_event_q, &e, 0) != pdTRUE) {
    LOGW("evt", "queue full, dropping kind=%d", (int)e.kind);
  }
}

static void parse_line() {
  s_linebuf[s_pos] = '\0';
  if (s_pos == 0) return;
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, s_linebuf);
  if (err) {
    LOGW("uart", "bad json: %.40s", s_linebuf);
    return;
  }
  translate_and_enqueue(doc);
}

void uart_link_init() {
  Serial.begin(UART_BAUD);
  Serial.setRxBufferSize(1024);
  Serial.setTimeout(10);
}

void uart_link_task(void* /*arg*/) {
  for (;;) {
    // RX: drain whatever bytes are available.
    while (Serial.available() > 0) {
      int b = Serial.read();
      if (b < 0) break;
      char c = (char)b;
      if (c == '\r') continue;
      if (c == '\n') {
        parse_line();
        s_pos = 0;
        continue;
      }
      if (s_pos < UART_LINE_MAX - 1) {
        s_linebuf[s_pos++] = c;
      } else {
        // overflow: reset; the rest of the line is forfeit
        LOGW("uart", "line overflow, resetting");
        s_pos = 0;
      }
    }

    // TX: drain outbound queue.
    outbound_msg_t out;
    while (xQueueReceive(g_outbound_q, &out, 0) == pdTRUE) {
      Serial.write((const uint8_t*)out.json, strlen(out.json));
      Serial.write('\n');
    }

    vTaskDelay(pdMS_TO_TICKS(5));
  }
}
```

- [ ] **Step 3: Remove the temporary `outbound_post` stub from `main.cpp` (added in Task 4)**

The real `outbound_post` is now provided by `uart_link.cpp`. Delete the stub line:

```cpp
// DELETE THIS LINE:
extern "C" void outbound_post(const struct outbound_msg_t*) { /* stub, removed in Task 5 */ }
```

- [ ] **Step 4: Build (will fail — `main.cpp` does not yet declare `g_event_q`, `g_outbound_q`)**

Add minimal declarations to `firmware/src/main.cpp` (these become the real definitions in Task 9):

```cpp
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
QueueHandle_t g_event_q = nullptr;
QueueHandle_t g_outbound_q = nullptr;
```

Run: `cd firmware && pio run`
Expected: SUCCESS.

- [ ] **Step 5: Commit**

```bash
cd /home/nguyenvd/workspace/smart_gate
git add firmware/src/uart_link.h firmware/src/uart_link.cpp firmware/src/main.cpp
git commit -m "feat(firmware): add uart_link JSON Lines RX/TX module"
```

---

## Task 6: `rfid` module (MFRC522 polling task)

**Files:**
- Create: `firmware/src/rfid.h`
- Create: `firmware/src/rfid.cpp`

- [ ] **Step 1: Create `firmware/src/rfid.h`**

```cpp
#pragma once

void rfid_init();
void rfid_task(void* arg);
```

- [ ] **Step 2: Create `firmware/src/rfid.cpp`**

```cpp
#include "rfid.h"
#include "../include/config.h"
#include "../include/events.h"
#include "../include/log.h"
#include "uart_link.h"
#include "allowlist.h"
#include <SPI.h>
#include <MFRC522.h>
#include <string.h>

static MFRC522 s_rc522(PIN_RC522_CS, PIN_RC522_RST);

static void uid_to_hex(const MFRC522::Uid& uid, char* out, size_t out_n) {
  size_t pos = 0;
  for (byte i = 0; i < uid.size && pos + 2 < out_n; ++i) {
    snprintf(out + pos, out_n - pos, "%02x", uid.uidByte[i]);
    pos += 2;
  }
  if (pos < out_n) out[pos] = '\0';
}

void rfid_init() {
  SPI.begin(PIN_RC522_SCK, PIN_RC522_MISO, PIN_RC522_MOSI, PIN_RC522_CS);
  s_rc522.PCD_Init();
}

void rfid_task(void* /*arg*/) {
  for (;;) {
    vTaskDelay(pdMS_TO_TICKS(RFID_POLL_INTERVAL_MS));
    if (!s_rc522.PICC_IsNewCardPresent()) continue;
    if (!s_rc522.PICC_ReadCardSerial()) continue;

    char uid_hex[16];
    uid_to_hex(s_rc522.uid, uid_hex, sizeof uid_hex);

    event_t e = {};
    e.src = SRC_RFID;
    e.kind = EV_RFID_SCAN;
    strncpy(e.uid, uid_hex, sizeof e.uid - 1);

    char name[32] = {0};
    bool granted = allowlist_lookup(uid_hex, name, sizeof name);
    e.i1 = granted ? 1 : 0;
    if (granted) strncpy(e.name, name, sizeof e.name - 1);

    if (xQueueSend(g_event_q, &e, 0) != pdTRUE) {
      LOGW("evt", "queue full, dropping rfid scan uid=%s", uid_hex);
    }

    s_rc522.PICC_HaltA();
    s_rc522.PCD_StopCrypto1();
  }
}
```

- [ ] **Step 3: Build**

Run: `cd firmware && pio run`
Expected: SUCCESS. (rfid_init/rfid_task are not yet called from main; they compile as standalone.)

- [ ] **Step 4: Commit**

```bash
cd /home/nguyenvd/workspace/smart_gate
git add firmware/src/rfid.h firmware/src/rfid.cpp
git commit -m "feat(firmware): add MFRC522 RFID polling task"
```

---

## Task 7: `sensor` module (HC-SR04 polling + debounce)

**Files:**
- Create: `firmware/src/sensor.h`
- Create: `firmware/src/sensor.cpp`

- [ ] **Step 1: Create `firmware/src/sensor.h`**

```cpp
#pragma once

void sensor_init();
void sensor_task(void* arg);
```

- [ ] **Step 2: Create `firmware/src/sensor.cpp`**

```cpp
#include "sensor.h"
#include "../include/config.h"
#include "../include/events.h"
#include "../include/log.h"
#include "uart_link.h"
#include <Arduino.h>

static int read_distance_cm() {
  digitalWrite(PIN_SR04_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_SR04_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_SR04_TRIG, LOW);
  unsigned long us = pulseIn(PIN_SR04_ECHO, HIGH, 30000UL);
  if (us == 0) return -1;  // timeout
  return (int)(us / 58UL);
}

void sensor_init() {
  pinMode(PIN_SR04_TRIG, OUTPUT);
  pinMode(PIN_SR04_ECHO, INPUT);
  digitalWrite(PIN_SR04_TRIG, LOW);
}

void sensor_task(void* /*arg*/) {
  int below_count = 0;
  int above_count = 0;
  bool in_passage = false;
  uint32_t passage_started_ms = 0;
  int trigger_distance_cm = 0;
  uint32_t no_echo_ms = 0;

  for (;;) {
    vTaskDelay(pdMS_TO_TICKS(SENSOR_POLL_INTERVAL_MS));
    int cm = read_distance_cm();
    uint32_t now = millis();

    if (cm < 0) {
      no_echo_ms += SENSOR_POLL_INTERVAL_MS;
      if (no_echo_ms >= 30000) {
        LOGW("sensor", "no echo for 30s");
        no_echo_ms = 0;
      }
      continue;
    }
    no_echo_ms = 0;

    if (cm < SENSOR_TRIGGER_CM) {
      below_count++;
      above_count = 0;
      if (!in_passage && below_count >= SENSOR_DEBOUNCE_COUNT) {
        in_passage = true;
        passage_started_ms = now;
        trigger_distance_cm = cm;
      }
    } else {
      above_count++;
      below_count = 0;
      if (in_passage && above_count >= SENSOR_DEBOUNCE_COUNT) {
        in_passage = false;
        event_t e = {};
        e.src = SRC_SENSOR;
        e.kind = EV_PASSAGE_DETECTED;
        e.i1 = trigger_distance_cm;
        e.i2 = (int32_t)(now - passage_started_ms);
        if (xQueueSend(g_event_q, &e, 0) != pdTRUE) {
          LOGW("evt", "queue full, dropping passage");
        }
      }
    }
  }
}
```

- [ ] **Step 3: Build**

Run: `cd firmware && pio run`
Expected: SUCCESS.

- [ ] **Step 4: Commit**

```bash
cd /home/nguyenvd/workspace/smart_gate
git add firmware/src/sensor.h firmware/src/sensor.cpp
git commit -m "feat(firmware): add HC-SR04 passage sensor task"
```

---

## Task 8: `gate_fsm` module (state machine + handlers)

**Files:**
- Create: `firmware/src/gate_fsm.h`
- Create: `firmware/src/gate_fsm.cpp`

- [ ] **Step 1: Create `firmware/src/gate_fsm.h`**

```cpp
#pragma once
#include "freertos/FreeRTOS.h"
#include "freertos/timers.h"
#include "../include/events.h"

enum GateState { S_IDLE, S_OPENING, S_OPEN_WAIT, S_TIMEOUT_WARN, S_CLOSING };

// Globals owned by main.cpp:
extern TimerHandle_t g_open_reached_timer;
extern TimerHandle_t g_passage_timeout_timer;
extern TimerHandle_t g_warn_giveup_timer;
extern TimerHandle_t g_close_reached_timer;
extern TimerHandle_t g_heartbeat_timer;

void gate_fsm_init();
void gate_fsm_task(void* arg);

// Timer callbacks (used by main.cpp's xTimerCreate calls):
void cb_open_reached(TimerHandle_t);
void cb_passage_timeout(TimerHandle_t);
void cb_warn_giveup(TimerHandle_t);
void cb_close_reached(TimerHandle_t);
void cb_heartbeat(TimerHandle_t);
```

- [ ] **Step 2: Create `firmware/src/gate_fsm.cpp`**

```cpp
#include "gate_fsm.h"
#include "../include/config.h"
#include "../include/log.h"
#include "../include/version.h"
#include "uart_link.h"
#include "servo_drv.h"
#include "lcd_drv.h"
#include "buzzer_drv.h"
#include "allowlist.h"
#include <ArduinoJson.h>
#include <Preferences.h>
#include <esp_system.h>
#include <esp_heap_caps.h>
#include <esp_task_wdt.h>
#include <string.h>

static GateState s_state = S_IDLE;
static uint32_t s_passage_timeout_ms = DEFAULT_PASSAGE_TIMEOUT_MS;

// === Helpers ===

static void emit_ack(uint32_t id, const char* verb, JsonDocument& data) {
  if (id == 0) return;
  JsonDocument doc;
  doc["type"] = "ack";
  doc["id"]   = id;
  doc["v"]    = verb;
  doc["data"] = data;
  outbound_msg_t out;
  size_t w = serializeJson(doc, out.json, sizeof out.json);
  if (w == 0 || w >= sizeof out.json) { LOGE("ack", "serialize fail"); return; }
  outbound_send(out);
}

static void emit_ack_ok(uint32_t id, const char* verb) {
  JsonDocument data; data["ok"] = true;
  emit_ack(id, verb, data);
}

static void emit_ack_err(uint32_t id, const char* verb, const char* err) {
  JsonDocument data; data["ok"] = false; data["err"] = err;
  emit_ack(id, verb, data);
}

static void emit_evt_gate(const char* state_str) {
  JsonDocument doc;
  doc["type"] = "evt";
  doc["v"]    = "gate";
  doc["data"]["state"] = state_str;
  outbound_msg_t out;
  size_t w = serializeJson(doc, out.json, sizeof out.json);
  if (w > 0 && w < sizeof out.json) outbound_send(out);
}

static void emit_evt_rfid(const char* uid, bool granted, const char* name) {
  JsonDocument doc;
  doc["type"] = "evt";
  doc["v"]    = "rfid";
  doc["data"]["uid"]    = uid;
  doc["data"]["result"] = granted ? "granted" : "denied";
  if (granted) doc["data"]["name"] = name;
  outbound_msg_t out;
  size_t w = serializeJson(doc, out.json, sizeof out.json);
  if (w > 0 && w < sizeof out.json) outbound_send(out);
}

static void emit_evt_passage(int32_t cm, int32_t ms) {
  JsonDocument doc;
  doc["type"] = "evt";
  doc["v"]    = "person_passed";
  doc["data"]["distance_cm"] = cm;
  doc["data"]["ms"]          = ms;
  outbound_msg_t out;
  size_t w = serializeJson(doc, out.json, sizeof out.json);
  if (w > 0 && w < sizeof out.json) outbound_send(out);
}

static const char* state_name(GateState s) {
  switch (s) {
    case S_IDLE:        return "idle";
    case S_OPENING:     return "opening";
    case S_OPEN_WAIT:   return "open";
    case S_TIMEOUT_WARN:return "timeout_warn";
    case S_CLOSING:     return "closing";
  }
  return "?";
}

// === Always-on command handlers ===

static void handle_ping(const event_t& e)   { emit_ack_ok(e.cmd_id, "ping"); }

static void handle_status(const event_t& e) {
  if (e.cmd_id == 0) return;
  JsonDocument data;
  data["uptime_s"]  = (uint32_t)(millis() / 1000);
  data["free_heap"] = (uint32_t)esp_get_free_heap_size();
  data["gate"]      = state_name(s_state);
  data["fw"]        = FW_VERSION;
  emit_ack(e.cmd_id, "status", data);
}

static void handle_list(const event_t& e) {
  if (e.cmd_id == 0) return;
  char buf[768];
  size_t w = allowlist_list_json(buf, sizeof buf);
  JsonDocument data;
  if (w == 0) {
    data["uids"] = JsonArray();
  } else {
    JsonDocument tmp;
    deserializeJson(tmp, buf);
    data["uids"] = tmp.as<JsonArray>();
  }
  emit_ack(e.cmd_id, "list_uids", data);
}

static void handle_add(const event_t& e) {
  int total = allowlist_add(e.uid, e.name);
  if (total == -1)       emit_ack_err(e.cmd_id, "add_uid", "full");
  else if (total == -2)  emit_ack_err(e.cmd_id, "add_uid", "nvs_write");
  else {
    JsonDocument data; data["ok"] = true; data["total"] = total;
    emit_ack(e.cmd_id, "add_uid", data);
  }
}

static void handle_remove(const event_t& e) {
  if (allowlist_remove(e.uid)) emit_ack_ok(e.cmd_id, "remove_uid");
  else                          emit_ack_err(e.cmd_id, "remove_uid", "not_found");
}

static void handle_config(const event_t& e) {
  Preferences cfg;
  cfg.begin(NVS_NS_CONFIG, false);
  if (e.i1 != INT32_MIN) {
    s_passage_timeout_ms = (uint32_t)e.i1 * 1000;
    cfg.putUInt("pass_to_ms", s_passage_timeout_ms);
  }
  int open_deg  = servo_open_deg();
  int close_deg = servo_close_deg();
  if (e.i2 != INT32_MIN) open_deg  = e.i2;
  if (e.i3 != INT32_MIN) close_deg = e.i3;
  servo_set_angles(open_deg, close_deg);
  if (e.i2 != INT32_MIN) cfg.putInt("open_deg", open_deg);
  if (e.i3 != INT32_MIN) cfg.putInt("close_deg", close_deg);
  cfg.end();
  emit_ack_ok(e.cmd_id, "config");
}

// === FSM transitions ===

static void enter_idle() {
  s_state = S_IDLE;
  emit_evt_gate("closed");
  lcd_show_idle();
}

static void start_open() {
  s_state = S_OPENING;
  emit_evt_gate("opening");
  lcd_show_opening();
  servo_open();
  xTimerStart(g_open_reached_timer, 0);
}

static void on_open_reached() {
  if (s_state != S_OPENING) return;
  s_state = S_OPEN_WAIT;
  emit_evt_gate("open");
  buzzer_beep_ok();
  xTimerChangePeriod(g_passage_timeout_timer, pdMS_TO_TICKS(s_passage_timeout_ms), 0);
  xTimerStart(g_passage_timeout_timer, 0);
}

static void on_passage(const event_t& e) {
  if (s_state != S_OPEN_WAIT && s_state != S_TIMEOUT_WARN) return;
  xTimerStop(g_passage_timeout_timer, 0);
  xTimerStop(g_warn_giveup_timer, 0);
  buzzer_stop_warn_pattern();
  emit_evt_passage(e.i1, e.i2);
  start_closing();
}

static void start_closing() {
  s_state = S_CLOSING;
  emit_evt_gate("closing");
  lcd_show_closing();
  servo_close();
  xTimerStart(g_close_reached_timer, 0);
}

static void on_close_reached() {
  if (s_state != S_CLOSING) return;
  enter_idle();
}

static void on_passage_timeout() {
  if (s_state != S_OPEN_WAIT) return;
  s_state = S_TIMEOUT_WARN;
  emit_evt_gate("timeout_warn");
  lcd_show_warn();
  buzzer_start_warn_pattern();
  xTimerStart(g_warn_giveup_timer, 0);
}

static void on_warn_giveup() {
  if (s_state != S_TIMEOUT_WARN) return;
  buzzer_stop_warn_pattern();
  start_closing();
}

static void force_close(uint32_t cmd_id) {
  xTimerStop(g_passage_timeout_timer, 0);
  xTimerStop(g_warn_giveup_timer, 0);
  buzzer_stop_warn_pattern();
  if (s_state != S_IDLE && s_state != S_CLOSING) {
    start_closing();
  }
  emit_ack_ok(cmd_id, "close");
}

// === Event dispatch ===

static void handle_event(const event_t& e) {
  // Always-on commands
  switch (e.kind) {
    case EV_CMD_PING:        handle_ping(e);   return;
    case EV_CMD_STATUS:      handle_status(e); return;
    case EV_CMD_LIST_UIDS:   handle_list(e);   return;
    case EV_CMD_ADD_UID:     handle_add(e);    return;
    case EV_CMD_REMOVE_UID:  handle_remove(e); return;
    case EV_CMD_CONFIG:      handle_config(e); return;
    case EV_CMD_CLOSE:       force_close(e.cmd_id); return;
    default: break;
  }

  // RFID always emits the event regardless of state
  if (e.kind == EV_RFID_SCAN) {
    bool granted = (e.i1 == 1);
    emit_evt_rfid(e.uid, granted, granted ? e.name : "");
    if (!granted) {
      lcd_show_denied();
      buzzer_beep_err();
      return;
    }
    // Granted: act on gate
    if (s_state == S_IDLE) {
      if (e.name[0] != '\0') lcd_show_name(e.name);
      start_open();
    } else if (s_state == S_OPEN_WAIT) {
      // hold-open semantics: restart timer
      xTimerStop(g_passage_timeout_timer, 0);
      xTimerChangePeriod(g_passage_timeout_timer, pdMS_TO_TICKS(s_passage_timeout_ms), 0);
      xTimerStart(g_passage_timeout_timer, 0);
    }
    return;
  }

  if (e.kind == EV_CMD_OPEN) {
    if (s_state == S_IDLE) {
      start_open();
      emit_ack_ok(e.cmd_id, "open");
    } else if (s_state == S_OPEN_WAIT) {
      xTimerStop(g_passage_timeout_timer, 0);
      xTimerChangePeriod(g_passage_timeout_timer, pdMS_TO_TICKS(s_passage_timeout_ms), 0);
      xTimerStart(g_passage_timeout_timer, 0);
      emit_ack_ok(e.cmd_id, "open");
    } else {
      emit_ack_err(e.cmd_id, "open", "busy");
    }
    return;
  }

  if (e.kind == EV_PASSAGE_DETECTED) { on_passage(e); return; }
  if (e.kind == EV_T_OPEN_REACHED)   { on_open_reached(); return; }
  if (e.kind == EV_T_PASSAGE_TIMEOUT){ on_passage_timeout(); return; }
  if (e.kind == EV_T_WARN_GIVEUP)    { on_warn_giveup(); return; }
  if (e.kind == EV_T_CLOSE_REACHED)  { on_close_reached(); return; }
}

// === Timer callbacks: post events to event_q so FSM is single-threaded ===

static void post_timer_event(EventKind k) {
  event_t e = {};
  e.src = SRC_TIMER;
  e.kind = k;
  xQueueSend(g_event_q, &e, 0);
}

void cb_open_reached(TimerHandle_t)    { post_timer_event(EV_T_OPEN_REACHED); }
void cb_passage_timeout(TimerHandle_t) { post_timer_event(EV_T_PASSAGE_TIMEOUT); }
void cb_warn_giveup(TimerHandle_t)     { post_timer_event(EV_T_WARN_GIVEUP); }
void cb_close_reached(TimerHandle_t)   { post_timer_event(EV_T_CLOSE_REACHED); }

void cb_heartbeat(TimerHandle_t) {
  JsonDocument doc;
  doc["type"] = "evt";
  doc["v"]    = "heartbeat";
  doc["data"]["uptime_s"]  = (uint32_t)(millis() / 1000);
  doc["data"]["free_heap"] = (uint32_t)esp_get_free_heap_size();
  doc["data"]["gate"]      = state_name(s_state);
  outbound_msg_t out;
  size_t w = serializeJson(doc, out.json, sizeof out.json);
  if (w > 0 && w < sizeof out.json) outbound_send(out);
}

// === Init + task ===

void gate_fsm_init() {
  // Load runtime config from NVS
  Preferences cfg;
  cfg.begin(NVS_NS_CONFIG, true);
  s_passage_timeout_ms = cfg.getUInt("pass_to_ms", DEFAULT_PASSAGE_TIMEOUT_MS);
  int od = cfg.getInt("open_deg", DEFAULT_SERVO_OPEN_DEG);
  int cd = cfg.getInt("close_deg", DEFAULT_SERVO_CLOSE_DEG);
  cfg.end();
  servo_set_angles(od, cd);
  s_state = S_IDLE;
}

void gate_fsm_task(void* /*arg*/) {
  esp_task_wdt_add(NULL);  // subscribe self
  event_t e;
  for (;;) {
    esp_task_wdt_reset();
    if (xQueueReceive(g_event_q, &e, pdMS_TO_TICKS(1000)) == pdTRUE) {
      handle_event(e);
    }
    // No event for 1s → loop back, reset WDT.
  }
}
```

- [ ] **Step 3: Build**

Run: `cd firmware && pio run`
Expected: SUCCESS. Timer globals are declared but not yet defined — they're defined in `main.cpp` in Task 9, but `pio` links late, so the build of `gate_fsm.cpp` itself should succeed and **the link will fail** with undefined references to `g_open_reached_timer` etc. That's expected; add temporary `nullptr` definitions to `main.cpp` (these become real in Task 9):

```cpp
TimerHandle_t g_open_reached_timer = nullptr;
TimerHandle_t g_passage_timeout_timer = nullptr;
TimerHandle_t g_warn_giveup_timer = nullptr;
TimerHandle_t g_close_reached_timer = nullptr;
TimerHandle_t g_heartbeat_timer = nullptr;
```

Re-run: `cd firmware && pio run`
Expected: SUCCESS.

- [ ] **Step 4: Commit**

```bash
cd /home/nguyenvd/workspace/smart_gate
git add firmware/src/gate_fsm.h firmware/src/gate_fsm.cpp firmware/src/main.cpp
git commit -m "feat(firmware): add gate state machine + handlers"
```

---

## Task 9: `main.cpp` boot sequence + task creation

**Files:**
- Modify: `firmware/src/main.cpp` (replace entirely)

- [ ] **Step 1: Replace `firmware/src/main.cpp` with the full boot sequence**

```cpp
#include <Arduino.h>
#include <esp_task_wdt.h>
#include <esp_system.h>
#include <esp_heap_caps.h>
#include <ArduinoJson.h>
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/timers.h"

#include "../include/config.h"
#include "../include/events.h"
#include "../include/version.h"
#include "../include/log.h"

#include "uart_link.h"
#include "rfid.h"
#include "sensor.h"
#include "gate_fsm.h"
#include "servo_drv.h"
#include "lcd_drv.h"
#include "buzzer_drv.h"
#include "allowlist.h"

// === Global queues + timers (extern'd in module headers) ===
QueueHandle_t g_event_q    = nullptr;
QueueHandle_t g_outbound_q = nullptr;
TimerHandle_t g_open_reached_timer    = nullptr;
TimerHandle_t g_passage_timeout_timer = nullptr;
TimerHandle_t g_warn_giveup_timer     = nullptr;
TimerHandle_t g_close_reached_timer   = nullptr;
TimerHandle_t g_heartbeat_timer       = nullptr;

static const char* reset_reason_string() {
  switch (esp_reset_reason()) {
    case ESP_RST_POWERON:  return "power_on";
    case ESP_RST_SW:       return "sw_reset";
    case ESP_RST_PANIC:    return "panic";
    case ESP_RST_INT_WDT:  return "watchdog";
    case ESP_RST_TASK_WDT: return "watchdog";
    case ESP_RST_WDT:      return "watchdog";
    case ESP_RST_BROWNOUT: return "brownout";
    default:               return "other";
  }
}

static void emit_boot_event() {
  JsonDocument doc;
  doc["type"] = "evt";
  doc["v"]    = "boot";
  doc["data"]["fw"]            = FW_VERSION;
  doc["data"]["free_heap"]     = (uint32_t)esp_get_free_heap_size();
  doc["data"]["reset_reason"]  = reset_reason_string();
  outbound_msg_t out;
  size_t w = serializeJson(doc, out.json, sizeof out.json);
  if (w > 0 && w < sizeof out.json) outbound_send(out);
}

void setup() {
  // 1. Status LED
  pinMode(PIN_LED_STATUS, OUTPUT);
  digitalWrite(PIN_LED_STATUS, LOW);

  // 2. UART up early (so logs work)
  uart_link_init();

  // 3. NVS / allowlist
  allowlist_init();

  // 4. Peripheral init
  servo_init();
  lcd_init();
  buzzer_init();
  rfid_init();
  sensor_init();

  // 5. Queues
  g_event_q    = xQueueCreate(EVENT_QUEUE_LEN,    sizeof(event_t));
  g_outbound_q = xQueueCreate(OUTBOUND_QUEUE_LEN, sizeof(outbound_msg_t));
  if (!g_event_q || !g_outbound_q) {
    ESP_LOGE("main", "queue alloc failed");
    while (1) vTaskDelay(pdMS_TO_TICKS(1000));
  }

  // 6. Timers
  g_open_reached_timer    = xTimerCreate("openR", pdMS_TO_TICKS(DEFAULT_OPEN_REACHED_MS),   pdFALSE, nullptr, cb_open_reached);
  g_passage_timeout_timer = xTimerCreate("passT", pdMS_TO_TICKS(DEFAULT_PASSAGE_TIMEOUT_MS),pdFALSE, nullptr, cb_passage_timeout);
  g_warn_giveup_timer     = xTimerCreate("warnG", pdMS_TO_TICKS(DEFAULT_WARN_GIVEUP_MS),    pdFALSE, nullptr, cb_warn_giveup);
  g_close_reached_timer   = xTimerCreate("closeR",pdMS_TO_TICKS(DEFAULT_CLOSE_REACHED_MS),  pdFALSE, nullptr, cb_close_reached);
  g_heartbeat_timer       = xTimerCreate("hb",    pdMS_TO_TICKS(HEARTBEAT_INTERVAL_MS),     pdTRUE,  nullptr, cb_heartbeat);

  // 7. FSM init (loads NVS config, applies servo angles)
  gate_fsm_init();

  // 8. Task watchdog: 8s timeout, panic on expiry
  esp_task_wdt_init(8, true);

  // 9. Spawn tasks
  xTaskCreatePinnedToCore(uart_link_task,  "uart_link",  4096, nullptr, 3, nullptr, 0);
  xTaskCreatePinnedToCore(rfid_task,       "rfid",       3072, nullptr, 2, nullptr, 1);
  xTaskCreatePinnedToCore(sensor_task,     "sensor",     2048, nullptr, 2, nullptr, 1);
  xTaskCreatePinnedToCore(gate_fsm_task,   "gate_fsm",   4096, nullptr, 4, nullptr, 1);

  // 10. Start heartbeat
  xTimerStart(g_heartbeat_timer, 0);

  // 11. Boot event
  emit_boot_event();
  digitalWrite(PIN_LED_STATUS, HIGH);
}

void loop() {
  // All work is in FreeRTOS tasks.
  vTaskDelay(pdMS_TO_TICKS(1000));
}
```

- [ ] **Step 2: Build**

Run: `cd firmware && pio run`
Expected: SUCCESS. Compile + link should produce `.pio/build/esp32dev/firmware.elf` and `firmware.bin`. Memory usage report appears at the end; record it.

- [ ] **Step 3: Check binary size + RAM**

Run: `cd firmware && pio run -t size`
Expected: Output includes "RAM:   [=         ]  X.X% (used N bytes from 327680 bytes)" and "Flash: [==        ]  Y.Y% (used M bytes from ...)". Confirm RAM usage is < 50% (target ESP32 SRAM 320KB, current expected use ~80KB including FreeRTOS + libs).

- [ ] **Step 4: Commit**

```bash
cd /home/nguyenvd/workspace/smart_gate
git add firmware/src/main.cpp
git commit -m "feat(firmware): wire up boot sequence and FreeRTOS tasks"
```

---

## Task 10: Verify status LED + heartbeat behavior without hardware

**Files:**
- None — pure inspection task.

- [ ] **Step 1: Manual code review against spec §4 (UART verbs)**

Open `firmware/src/uart_link.cpp` and `firmware/src/gate_fsm.cpp`. For each verb in spec §4.3 and event in §4.4, confirm there's a code path producing the right JSON:

| Spec verb | Source line(s) |
| --- | --- |
| `cmd:open` | `uart_link.cpp::translate_and_enqueue` → `EV_CMD_OPEN` → `gate_fsm.cpp::handle_event::EV_CMD_OPEN` |
| `cmd:close` | `EV_CMD_CLOSE` → `force_close` |
| `cmd:add_uid` | `EV_CMD_ADD_UID` → `handle_add` |
| `cmd:remove_uid` | `EV_CMD_REMOVE_UID` → `handle_remove` |
| `cmd:list_uids` | `EV_CMD_LIST_UIDS` → `handle_list` |
| `cmd:config` | `EV_CMD_CONFIG` → `handle_config` |
| `cmd:status` | `EV_CMD_STATUS` → `handle_status` |
| `cmd:ping` | `EV_CMD_PING` → `handle_ping` |
| `evt:boot` | `main.cpp::emit_boot_event` |
| `evt:rfid` | `gate_fsm.cpp::emit_evt_rfid` |
| `evt:gate` | `gate_fsm.cpp::emit_evt_gate` |
| `evt:person_passed` | `gate_fsm.cpp::emit_evt_passage` |
| `evt:heartbeat` | `gate_fsm.cpp::cb_heartbeat` |
| `evt:log` | `log_emit.cpp::emit_log` |

If any row has no source line, the implementation is incomplete — go back to the appropriate earlier task. Otherwise mark this step done.

- [ ] **Step 2: Manual code review against spec §4.5 (gate state machine)**

In `gate_fsm.cpp::handle_event`, walk each transition from spec §4.5 and confirm:

- `IDLE` + `cmd:open` or RFID granted → `start_open()` ✓
- `OPENING` + open-reached timer → `S_OPEN_WAIT` ✓ (`on_open_reached`)
- `OPEN_WAIT` + passage → `start_closing()` ✓ (`on_passage`)
- `OPEN_WAIT` + 10 s elapsed → `S_TIMEOUT_WARN` ✓ (`on_passage_timeout`)
- `TIMEOUT_WARN` + passage → `start_closing()` ✓
- `TIMEOUT_WARN` + 5 s elapsed → `start_closing()` ✓ (`on_warn_giveup`)
- `CLOSING` + close-reached timer → `enter_idle()` ✓ (`on_close_reached`)

- [ ] **Step 3: Confirm log macros wire correctly**

Run: `grep -rn 'LOGI\|LOGW\|LOGE' firmware/src/ firmware/include/`
Expected: every match resolves through `log.h`, which transitively includes `log_emit.h`. No raw `printf` or `Serial.println` outside of `uart_link.cpp::uart_link_task` TX drain.

- [ ] **Step 4: No commit (review-only task)**

---

## Task 11: README — pin map, build/flash workflow, acceptance test scenarios

**Files:**
- Modify: `firmware/README.md` (replace entirely)

- [ ] **Step 1: Rewrite `firmware/README.md`**

```markdown
# smart_gate ESP32 firmware

Implements the firmware described in [`../docs/superpowers/specs/2026-05-22-esp32-firmware-design.md`](../docs/superpowers/specs/2026-05-22-esp32-firmware-design.md).

Talks JSON Lines over USB-CDC to a Raspberry Pi 5. Operates the gate independently of the Pi if the link is lost; RFID auth is local via NVS allowlist.

## Toolchain

- [PlatformIO](https://platformio.org/) (CLI: `pio`).
- Framework: Arduino-ESP32.
- Board: ESP32-WROOM-32 DevKit.

## Pin map (mirrors architecture spec §5)

| GPIO | Peripheral |
| --- | --- |
| 1   | UART0 TX (USB-CDC) |
| 3   | UART0 RX (USB-CDC) |
| 2   | Onboard status LED |
| 5   | RC522 CS |
| 18  | RC522 SCK |
| 19  | RC522 MISO |
| 23  | RC522 MOSI |
| 17  | RC522 RST |
| 16  | RC522 IRQ (reserved; polling mode) |
| 21  | LCD I2C SDA |
| 22  | LCD I2C SCL |
| 27  | HC-SR04 TRIG |
| 26  | HC-SR04 ECHO (via voltage divider) |
| 13  | Servo SG90 PWM |
| 14  | Buzzer (via 2N3904 NPN) |

LCD I2C pull-up cut required — see architecture spec §5.2.

## Build

```bash
pio run
```

First build downloads platform + libraries (~2–5 min).

## Flash

```bash
# Pi pyserial app must release /dev/ttyUSB0 first.
pio run -t upload
```

Reset is automatic via DTR/RTS on CP2102.

## Monitor

```bash
pio device monitor
```

Press Ctrl+T then Ctrl+H for the picocom-style help.

## UART protocol

See architecture spec §4. JSON Lines, 115200 baud (USB-CDC ignores baud but app config is symmetric with Pi).

Send a `ping`:

```
{"id":1,"type":"cmd","v":"ping"}
```

Expect:

```
{"type":"ack","id":1,"v":"ping","data":{"ok":true}}
```

## Acceptance tests (manual)

| # | Scenario | Expected serial output |
| --- | --- | --- |
| 1 | Power on board | One line `{"type":"evt","v":"boot","data":{"fw":"1.0.0","free_heap":N,"reset_reason":"power_on"}}` within 500 ms |
| 2 | Send `{"id":1,"type":"cmd","v":"ping"}` | `{"type":"ack","id":1,"v":"ping","data":{"ok":true}}` within 100 ms |
| 3 | Scan whitelisted card | `evt:rfid granted` with `name`; `evt:gate opening` → `evt:gate open` after 300 ms; LCD `"Welcome: <name>"`; servo physically opens |
| 4 | Pass hand through HC-SR04 beam | `evt:person_passed` with `distance_cm` and `ms`; `evt:gate closing` → `evt:gate closed` |
| 5 | Scan non-whitelisted card | `evt:rfid denied`; buzzer triple-beep; no gate motion |
| 6 | `cmd:open` then leave alone | `evt:gate opening` → `evt:gate open`; after 10 s `evt:gate timeout_warn` + buzzer warn pattern; after 5 s `evt:gate closing` → `evt:gate closed` |
| 7 | `add_uid` → `list_uids` → reboot → `list_uids` | Second `list_uids` after reboot still contains added UID |
| 8 | `remove_uid` for unknown UID | `ack` with `{"ok":false,"err":"not_found"}` |
| 9 | `cmd:config {"close_timeout_s":3}` then `cmd:open` and idle | Timeout warning fires at 3 s instead of 10 s |
| 10 | Disconnect Pi USB, scan whitelisted card | RFID auth still works end-to-end (boards standalone) |
| 11 | Send malformed JSON | `evt:log warn` with `tag:"uart"`; next valid message still processed |
| 12 | Hold whitelisted card on reader | `evt:rfid granted` fires once; identical events suppressed until card removed |

Record pass/fail in `firmware/test-log.md` (create on first acceptance run).

## Troubleshooting

- **`pio run -t upload` fails with "Resource busy"** — another process holds `/dev/ttyUSB0`. Stop the Pi app or `fuser -k /dev/ttyUSB0`.
- **No serial output at all** — check USB cable (some are charge-only), check `pio device list` for the right port name.
- **LCD shows garbage** — pull-up cut not done (architecture spec §5.2). Cut the on-backpack 4.7 kΩ pull-ups, the carrier PCB pull-ups to 3V3 take over.
- **RFID never reads** — confirm SPI wiring; the RC522 module's onboard regulator drops 3V3 if there's a short.
- **HC-SR04 always reads 0** — confirm voltage divider on ECHO (5 V → 3.3 V). Direct 5 V to GPIO 26 over time damages the input.
- **Servo jitters** — 470 µF cap on 5 V rail not installed (architecture spec §2.2).
```

- [ ] **Step 2: Commit**

```bash
cd /home/nguyenvd/workspace/smart_gate
git add firmware/README.md
git commit -m "docs(firmware): pin map, build/flash, and acceptance tests"
```

---

## Task 12: Final build verification + commit

**Files:**
- None new; final smoke check.

- [ ] **Step 1: Clean and rebuild**

Run:
```bash
cd /home/nguyenvd/workspace/smart_gate/firmware
pio run -t clean && pio run
```

Expected: SUCCESS from clean. All 11 .cpp translation units compile. Final link succeeds.

- [ ] **Step 2: Capture memory report**

Run: `cd firmware && pio run -t size 2>&1 | tail -40`
Save the size table into a comment in this plan file (optional — not committed).

Expected ranges (sanity check):
- Flash usage: 800 KB – 1.2 MB (out of 1.3 MB app partition default)
- RAM usage at link time (static + initialized data): 30 KB – 60 KB (out of 320 KB)

If Flash > 1.2 MB, libraries may have brought in unneeded code; investigate before proceeding.

- [ ] **Step 3: Final commit (only if any uncommitted changes remain)**

```bash
cd /home/nguyenvd/workspace/smart_gate
git status
# If status shows nothing → all earlier task commits were sufficient.
# If status shows changes → review them, then:
git add firmware/
git commit -m "chore(firmware): final pass for ESP32 firmware MVP"
```

---

## Self-review

**Spec coverage:**
- §1 Overview → reflected in plan goal + module list. ✓
- §2 Toolchain + libraries → Task 0 (platformio.ini). ✓
- §3 Project layout → File Structure table + tasks 0–9. ✓
- §4 Configuration constants → Task 1 (config.h). ✓
- §5 Event types → Task 1 (events.h). ✓
- §6 Task model → Task 9 (xTaskCreatePinnedToCore calls match spec table). ✓
- §7.1 uart_link → Task 5. ✓
- §7.2 rfid → Task 6. ✓
- §7.3 sensor → Task 7. ✓
- §7.4 gate_fsm → Task 8 (with all sub-handlers). ✓
- §7.5 servo/lcd/buzzer drv → Task 3. ✓
- §7.6 allowlist → Task 2. ✓
- §8 Logging + error handling → Task 4 (log_emit) + Task 8 (queue-full handling). ✓
- §8.3 Watchdog → Task 8 (`esp_task_wdt_add` in gate_fsm_task) + Task 9 (`esp_task_wdt_init`). ✓
- §9 Boot sequence → Task 9. ✓
- §10 Testing strategy (manual scenarios) → Task 11 README. ✓
- §11 Build / flash / monitor → Task 11 README. ✓
- §12 Risks → README troubleshooting. ✓

**Placeholder scan:** No TBDs, no "implement later", no "similar to". Each step has explicit code or commands.

**Type consistency:**
- `event_t` defined Task 1, used identically in tasks 5/6/7/8/9. ✓
- `outbound_msg_t` ditto. ✓
- `GateState` enum defined Task 8, used only within `gate_fsm.cpp`. ✓
- Function names: `allowlist_lookup` / `allowlist_add` / `allowlist_remove` / `allowlist_list_json` / `allowlist_count` consistent across header (Task 2) and callers (Task 6, Task 8). ✓
- Driver names: `servo_open`/`servo_close` (not `gate_open`/`gate_close`) consistent. `lcd_show_idle`/`lcd_show_name`/etc. consistent. `buzzer_beep_ok`/`buzzer_beep_err`/`buzzer_start_warn_pattern`/`buzzer_stop_warn_pattern` consistent. ✓
- Globals: `g_event_q`, `g_outbound_q`, `g_open_reached_timer`, `g_passage_timeout_timer`, `g_warn_giveup_timer`, `g_close_reached_timer`, `g_heartbeat_timer` — names match between extern declarations (Tasks 5, 8) and definitions (Task 9). ✓
- `outbound_send` (Task 5) vs `outbound_post` (Task 4 C-linkage): both implemented in `uart_link.cpp` Task 5. ✓

No issues.

---

*End of plan.*
