#include "gate_fsm.h"
#include "../include/config.h"
#include "../include/log.h"
#include "../include/version.h"
#include "uart_link.h"
#include "servo_drv.h"
#include "lcd_drv.h"
#include "buzzer_drv.h"
#include "allowlist.h"
#include "sensor.h"
#include "rfid.h"
#include <ArduinoJson.h>
#include <Preferences.h>
#include <esp_system.h>
#include <esp_heap_caps.h>
#include <esp_task_wdt.h>
#include <string.h>

static GateState s_state = S_IDLE;
static uint32_t s_passage_timeout_ms = DEFAULT_PASSAGE_TIMEOUT_MS;
// True when buzzer warn pattern is sounding due to obstacle persisting >5s in S_OPEN_WAIT.
static bool s_obstacle_warn_active = false;
// Timestamp (millis()) of entry into S_OPEN_WAIT — used to ignore spurious
// passage events while the arm is still sweeping through the HC-SR04 cone.
static uint32_t s_open_wait_entered_ms = 0;

// Forward declarations for internal handlers used before definition:
static void start_closing();

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
  s_open_wait_entered_ms = millis();
  emit_evt_gate("open");
  buzzer_beep_ok_async();
  xTimerChangePeriod(g_passage_timeout_timer, pdMS_TO_TICKS(s_passage_timeout_ms), 0);
  xTimerStart(g_passage_timeout_timer, 0);
}

static void on_passage(const event_t& e) {
  // Arm-settle window: during the first 500 ms after the gate reaches OPEN,
  // the arm is still sweeping through the HC-SR04 cone and emits a spurious
  // EV_PASSAGE_DETECTED. Drop it WITHOUT touching the no-passage timeout
  // family — the original passage-timeout fallback must keep running so the
  // gate still closes if no real person arrives.
  if (s_state == S_OPEN_WAIT &&
      millis() - s_open_wait_entered_ms < 500) {
    return;
  }

  // Obstacle detected — stop the no-passage timeout family (someone is now in the beam).
  xTimerStop(g_passage_timeout_timer, 0);
  xTimerStop(g_warn_giveup_timer, 0);
  // S_TIMEOUT_WARN: user finally arrived during the no-passage warn — close immediately
  // as before (unchanged behavior).
  if (s_state == S_TIMEOUT_WARN) {
    buzzer_stop_warn_pattern();
    emit_evt_passage(e.i1, e.i2);
    start_closing();
    return;
  }
  if (s_state != S_OPEN_WAIT) return;
  // New behavior: don't close yet. Arm the 5s obstacle-persistent timer.
  // EV_OBSTACLE_CLEARED handler closes the gate if obstacle clears first.
  // Note: don't emit evt:person_passed here — EV_PASSAGE_DETECTED carries i2=0
  // (duration unknown at detect-edge). Emit at clear-edge with full dwell ms.
  xTimerChangePeriod(g_obstacle_warn_timer, pdMS_TO_TICKS(5000), 0);
  xTimerStart(g_obstacle_warn_timer, 0);
}

static void on_obstacle_cleared(const event_t& e) {
  if (s_state != S_OPEN_WAIT) return;
  xTimerStop(g_obstacle_warn_timer, 0);
  if (s_obstacle_warn_active) {
    buzzer_stop_warn_pattern();
    s_obstacle_warn_active = false;
  }
  // Emit person_passed with the full dwell duration (i2 = duration_ms in beam).
  emit_evt_passage(e.i1, e.i2);
  start_closing();
}

static void on_obstacle_warn_fired() {
  if (s_state != S_OPEN_WAIT) return;
  // Obstacle continuously present for 5s — start the warn pattern until it clears.
  buzzer_start_warn_pattern();
  s_obstacle_warn_active = true;
  LOGW("warn", "obstacle blocked >5s, buzzer warning");
}

static void start_closing() {
  // Defensive cleanup: mirror force_close() so any caller path that forgot to
  // stop the obstacle-warn timer/buzzer can't leak warn state into S_CLOSING.
  xTimerStop(g_obstacle_warn_timer, 0);
  if (s_obstacle_warn_active) buzzer_stop_warn_pattern();
  s_obstacle_warn_active = false;
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
  xTimerStop(g_obstacle_warn_timer, 0);
  buzzer_stop_warn_pattern();
  s_obstacle_warn_active = false;
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

  if (e.kind == EV_T_LCD_RESTORE) {
    if (s_state == S_IDLE) lcd_show_idle();
    return;
  }

  if (e.kind == EV_T_LCD_ICON_TICK) {
    lcd_update_icons(sensor_is_obstacle(), rfid_is_card_present());
    return;
  }

  if (e.kind == EV_RFID_SCAN) {
    bool granted = (e.i1 == 1);
    emit_evt_rfid(e.uid, granted, granted ? e.name : "");
    if (!granted) {
      lcd_show_denied();
      {
        int err = lcd_drv_last_i2c_err();
        if (err == 0) LOGI("i2c", "swipe uid=%s lcd_write ok", e.uid);
        else          LOGW("i2c", "swipe uid=%s lcd_write err=%d", e.uid, err);
      }
      buzzer_beep_err_async();
      xTimerChangePeriod(g_lcd_restore_timer, pdMS_TO_TICKS(2500), 0);
      xTimerStart(g_lcd_restore_timer, 0);
      return;
    }
    if (s_state == S_IDLE) {
      buzzer_beep_ok_async();   // immediate auth feedback
      if (e.name[0] != '\0') {
        lcd_show_name(e.name);
        int err = lcd_drv_last_i2c_err();
        if (err == 0) LOGI("i2c", "swipe uid=%s lcd_write ok", e.uid);
        else          LOGW("i2c", "swipe uid=%s lcd_write err=%d", e.uid, err);
      }
      start_open();
    } else if (s_state == S_OPEN_WAIT) {
      xTimerStop(g_passage_timeout_timer, 0);
      xTimerChangePeriod(g_passage_timeout_timer, pdMS_TO_TICKS(s_passage_timeout_ms), 0);
      xTimerStart(g_passage_timeout_timer, 0);
    }
    return;
  }

  if (e.kind == EV_CMD_OPEN) {
    if (s_state == S_IDLE) {
      buzzer_beep_ok_async();   // immediate auth feedback (face/QR via Pi cmd:open)
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
  if (e.kind == EV_OBSTACLE_CLEARED) { on_obstacle_cleared(e); return; }
  if (e.kind == EV_T_OPEN_REACHED)   { on_open_reached(); return; }
  if (e.kind == EV_T_PASSAGE_TIMEOUT){ on_passage_timeout(); return; }
  if (e.kind == EV_T_WARN_GIVEUP)    { on_warn_giveup(); return; }
  if (e.kind == EV_T_CLOSE_REACHED)  { on_close_reached(); return; }
  if (e.kind == EV_T_OBSTACLE_WARN_FIRED) { on_obstacle_warn_fired(); return; }
}

// === Timer callbacks ===

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
  Preferences cfg;
  // readOnly=false so the namespace is created on first boot if missing — opening
  // a non-existent namespace with readOnly=true logs an [E] nvs_open NOT_FOUND
  // and returns default values for every getter (boot log noise; defaults are
  // still applied below, but the spurious error message is misleading).
  cfg.begin(NVS_NS_CONFIG, false);
  s_passage_timeout_ms = cfg.getUInt("pass_to_ms", DEFAULT_PASSAGE_TIMEOUT_MS);
  int od = cfg.getInt("open_deg", DEFAULT_SERVO_OPEN_DEG);
  int cd = cfg.getInt("close_deg", DEFAULT_SERVO_CLOSE_DEG);
  cfg.end();
  servo_set_angles(od, cd);
  s_state = S_IDLE;
}

void gate_fsm_task(void* /*arg*/) {
  esp_task_wdt_add(NULL);
  event_t e;
  for (;;) {
    esp_task_wdt_reset();
    if (xQueueReceive(g_event_q, &e, pdMS_TO_TICKS(1000)) == pdTRUE) {
      handle_event(e);
    }
  }
}
