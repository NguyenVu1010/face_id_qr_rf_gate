#include "allowlist.h"
#include "../include/config.h"
#include "../include/log.h"
#include <Preferences.h>
#include <ArduinoJson.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

static Preferences prefs;
static SemaphoreHandle_t s_mtx = nullptr;
static bool s_degraded = false;

#define ALLOW_LOCK_RC(rc_on_timeout) do { \
    if (s_mtx == nullptr) return (rc_on_timeout); \
    if (xSemaphoreTake(s_mtx, pdMS_TO_TICKS(500)) != pdTRUE) { \
        LOGW("allowlist", "mutex timeout"); \
        return (rc_on_timeout); \
    } \
} while (0)
#define ALLOW_UNLOCK() xSemaphoreGive(s_mtx)

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
  s_mtx = xSemaphoreCreateMutex();
  if (!s_mtx) {
    LOGE("allowlist", "mutex create failed");
    s_degraded = true;
    return;
  }
  bool ok = prefs.begin(NVS_NS_ALLOWLIST, /*readOnly=*/false);
  if (!ok) {
    LOGE("nvs", "allowlist begin failed - running in degraded mode");
    s_degraded = true;
    return;
  }
  // Ensure index exists
  if (!prefs.isKey(NVS_INDEX_KEY)) {
    prefs.putString(NVS_INDEX_KEY, "[]");
  }
}

bool allowlist_lookup(const char* uid_hex, char* name_out, size_t name_out_n) {
  if (s_degraded) return false;   // safe-deny
  if (s_mtx == nullptr) return false;
  if (xSemaphoreTake(s_mtx, pdMS_TO_TICKS(500)) != pdTRUE) {
    LOGW("allowlist", "mutex timeout on lookup");
    return false;
  }
  bool result = false;
  if (prefs.isKey(uid_hex)) {
    String n = prefs.getString(uid_hex, "");
    if (n.length() > 0) {
      strncpy(name_out, n.c_str(), name_out_n - 1);
      name_out[name_out_n - 1] = '\0';
      result = true;
    }
  }
  xSemaphoreGive(s_mtx);
  return result;
}

static int allowlist_add_locked(const char* uid_hex, const char* name) {
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

int allowlist_add(const char* uid_hex, const char* name) {
  if (s_degraded) return -2;   // nvs error code
  ALLOW_LOCK_RC(-2);            // reuse -2 (nvs/timeout) — Pi handler treats both as "nvs failure"
  int r = allowlist_add_locked(uid_hex, name);
  ALLOW_UNLOCK();
  return r;
}

bool allowlist_remove(const char* uid_hex) {
  if (s_degraded) return false;
  if (s_mtx == nullptr) return false;
  if (xSemaphoreTake(s_mtx, pdMS_TO_TICKS(500)) != pdTRUE) {
    LOGW("allowlist", "mutex timeout on remove");
    return false;
  }
  bool result = false;
  if (prefs.isKey(uid_hex)) {
    JsonDocument doc;
    if (index_load(doc)) {
      JsonArray arr = doc.as<JsonArray>();
      // Rebuild without the target UID
      JsonDocument out;
      JsonArray out_arr = out.to<JsonArray>();
      for (JsonVariant v : arr) {
        if (strcmp(v.as<const char*>(), uid_hex) != 0) out_arr.add(v.as<const char*>());
      }
      index_save(out);
      prefs.remove(uid_hex);
      result = true;
    }
  }
  xSemaphoreGive(s_mtx);
  return result;
}

size_t allowlist_list_json(char* out_json, size_t out_json_n) {
  if (s_degraded) return 0;
  if (s_mtx == nullptr) return 0;
  if (xSemaphoreTake(s_mtx, pdMS_TO_TICKS(500)) != pdTRUE) {
    LOGW("allowlist", "mutex timeout on list");
    return 0;
  }
  size_t w = 0;
  JsonDocument idx;
  if (index_load(idx)) {
    JsonDocument out;
    JsonArray out_arr = out.to<JsonArray>();
    for (JsonVariant v : idx.as<JsonArray>()) {
      const char* uid = v.as<const char*>();
      String n = prefs.getString(uid, "");
      JsonObject o = out_arr.add<JsonObject>();
      o["uid"] = uid;
      o["name"] = n.c_str();
    }
    w = serializeJson(out, out_json, out_json_n);
    if (w == 0 || w >= out_json_n) w = 0;
  }
  xSemaphoreGive(s_mtx);
  return w;
}

size_t allowlist_count() {
  if (s_degraded) return 0;
  if (s_mtx == nullptr) return 0;
  if (xSemaphoreTake(s_mtx, pdMS_TO_TICKS(500)) != pdTRUE) {
    LOGW("allowlist", "mutex timeout on count");
    return 0;
  }
  size_t result = 0;
  JsonDocument doc;
  if (index_load(doc)) {
    result = doc.as<JsonArray>().size();
  }
  xSemaphoreGive(s_mtx);
  return result;
}
