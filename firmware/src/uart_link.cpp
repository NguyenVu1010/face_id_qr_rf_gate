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
    if (g_outbound_q) {
      outbound_msg_t out;
      while (xQueueReceive(g_outbound_q, &out, 0) == pdTRUE) {
        Serial.write((const uint8_t*)out.json, strlen(out.json));
        Serial.write('\n');
      }
    }

    vTaskDelay(pdMS_TO_TICKS(5));
  }
}
