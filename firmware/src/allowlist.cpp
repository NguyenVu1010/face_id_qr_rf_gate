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
