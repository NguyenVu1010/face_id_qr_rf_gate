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
static bool s_discarding = false;

// Per-boot-session replay guard. Any cmd with id <= s_last_cmd_id is
// rejected as a replay. Reset to 0 in uart_link_init() so a soft reboot
// starts fresh. Pi seeds its counter from int(time.time()) so IDs are
// monotonic across Pi restarts within the same ESP session.
static uint32_t s_last_cmd_id = 0;

// Emit a minimal ack with err so a Pi waiting on send_cmd() wakes
// immediately instead of timing out. Mirrors emit_ack_err() in
// gate_fsm.cpp but is duplicated here because that helper is file-static.
static void emit_replay_ack_err(uint32_t id, const char* verb) {
  if (id == 0) return;
  JsonDocument doc;
  doc["type"] = "ack";
  doc["id"]   = id;
  doc["v"]    = verb;
  doc["data"]["ok"]  = false;
  doc["data"]["err"] = "replay";
  outbound_msg_t out;
  size_t w = serializeJson(doc, out.json, sizeof out.json);
  if (w == 0 || w >= sizeof out.json) { LOGE("ack", "serialize fail"); return; }
  outbound_send(out);
}

static void translate_and_enqueue(JsonDocument& doc) {
  const char* type = doc["type"] | "";
  if (strcmp(type, "cmd") != 0) {
    LOGW("uart", "ignored non-cmd type='%s'", type);
    return;
  }
  const char* v = doc["v"] | "";

  // Strict id parsing + per-session replay guard. Reject missing /
  // non-numeric id, id == 0, and any id <= last seen. This closes the
  // trivial "record a cmd:open line over /dev/serial0 and replay it"
  // window. A determined attacker with full bus access can still inject
  // (id++) — that would need HMAC, which is out of scope here.
  JsonVariant id_v = doc["id"];
  if (!id_v.is<uint32_t>() && !id_v.is<int>()) {
    LOGW("uart", "cmd missing/invalid id");
    return;
  }
  uint32_t cmd_id = id_v.as<uint32_t>();
  if (cmd_id == 0) {
    LOGW("uart", "cmd id=0 rejected");
    return;
  }
  if (cmd_id <= s_last_cmd_id) {
    LOGW("uart", "cmd id %u replay (last=%u)",
         (unsigned)cmd_id, (unsigned)s_last_cmd_id);
    emit_replay_ack_err(cmd_id, v);
    return;
  }
  s_last_cmd_id = cmd_id;

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

// Pi link uses ESP32 UART1 (Serial1) on GPIO 32 (RX) / GPIO 25 (TX).
// UART0 (Serial, GPIO 1/3) is intentionally NOT used here — it stays free for
// `pio device monitor` debug log and `esptool.py` firmware flashing per
// architecture spec §4.1 / decision #26.

void uart_link_init() {
  // NOTE: arduino-esp32 2.0.x (espressif32@^6.0) reports
  //   [E] HardwareSerial setRxBufferSize: RX Buffer can't be resized when
  //       Serial is already running. Set it before calling begin().
  // when setRxBufferSize() is called AFTER begin(). However, calling it BEFORE
  // begin() on this version triggers a boot lock-up shortly after I2C init
  // (verified 2026-06-03: chip resets just past the "Bus already started in
  // Master Mode" log). Keeping the call after begin() — the [E] is cosmetic
  // and the RX buffer stays at the 256-byte default, which is sufficient for
  // our line-based JSON commands (< 200 bytes typical).
  Serial1.begin(UART_BAUD, SERIAL_8N1, PIN_PI_UART_RX, PIN_PI_UART_TX);
  Serial1.setRxBufferSize(1024);
  Serial1.setTimeout(10);
  s_pos = 0;
  s_discarding = false;
  s_last_cmd_id = 0;  // fresh replay counter on (soft) reboot
}

void uart_link_task(void* /*arg*/) {
  for (;;) {
    // RX: drain whatever bytes are available on the Pi UART link.
    while (Serial1.available() > 0) {
      int b = Serial1.read();
      if (b < 0) break;
      char c = (char)b;

      if (c == '\r') continue;   // strip CR (Windows CRLF)

      if (c == '\n') {
        if (s_discarding) {
          // Oversized line ends here — drop it, do NOT parse the corrupted tail.
          s_pos = 0;
          s_discarding = false;
          continue;
        }
        parse_line();
        s_pos = 0;
        continue;
      }

      if (s_discarding) continue;   // drop tail bytes silently until next '\n'

      if (s_pos >= UART_LINE_MAX - 1) {
        LOGW("uart", "line overflow, discarding until next \\n");
        s_discarding = true;
        s_pos = 0;
        continue;
      }

      s_linebuf[s_pos++] = c;
    }

    // TX: drain outbound queue → Pi UART link.
    if (g_outbound_q) {
      outbound_msg_t out;
      while (xQueueReceive(g_outbound_q, &out, 0) == pdTRUE) {
        Serial1.write((const uint8_t*)out.json, strlen(out.json));
        Serial1.write('\n');
      }
    }

    vTaskDelay(pdMS_TO_TICKS(5));
  }
}
