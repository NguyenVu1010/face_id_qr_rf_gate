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
