#include "sensor.h"
#include "../include/config.h"
#include "../include/events.h"
#include "../include/log.h"
#include "uart_link.h"
#include <Arduino.h>

static volatile bool s_obstacle_present = false;

// Phase 3.4 — median-of-3 over the last 3 valid samples + persistent fault notify.
static int s_last3[3] = {-1, -1, -1};
static int s_last3_idx = 0;
static int s_no_echo_streak = 0;     // consecutive no-echo samples
static bool s_fault_emitted = false;  // one-shot per fault session

static int read_distance_cm() {
  digitalWrite(PIN_SR04_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_SR04_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_SR04_TRIG, LOW);
  unsigned long us = pulseIn(PIN_SR04_ECHO, HIGH, 30000UL);
  if (us == 0)    return -1;  // timeout / no echo
  if (us < 116)   return -1;  // < 2 cm: physically impossible for HC-SR04
  if (us > 23200) return -1;  // > 400 cm: ghost echo, out of spec
  return (int)(us / 58UL);
}

static int median3(int a, int b, int c) {
  if ((a <= b && b <= c) || (c <= b && b <= a)) return b;
  if ((b <= a && a <= c) || (c <= a && a <= b)) return a;
  return c;
}

// Returns -1 on no echo; otherwise the median of the last 3 valid samples
// (or the raw value while the window is still warming up).
static int sensor_read_filtered_cm() {
  int raw = read_distance_cm();
  if (raw < 0) {
    s_no_echo_streak++;
    // 150 s threshold at SENSOR_POLL_INTERVAL_MS cadence. Emit once per fault session.
    if (!s_fault_emitted &&
        (uint32_t)s_no_echo_streak * SENSOR_POLL_INTERVAL_MS >= 150000UL) {
      LOGW("sensor", "sensor_fault no echo persistent");
      s_fault_emitted = true;
    }
    return -1;
  }
  // Valid sample — reset fault tracking and slot into ring buffer.
  s_no_echo_streak = 0;
  s_fault_emitted = false;
  s_last3[s_last3_idx] = raw;
  s_last3_idx = (s_last3_idx + 1) % 3;
  if (s_last3[0] < 0 || s_last3[1] < 0 || s_last3[2] < 0) return raw;
  return median3(s_last3[0], s_last3[1], s_last3[2]);
}

void sensor_init() {
  pinMode(PIN_SR04_TRIG, OUTPUT);
  // INPUT_PULLDOWN: a disconnected ECHO wire reads idle-low instead of
  // floating, preventing spurious "very close" pulses.
  pinMode(PIN_SR04_ECHO, INPUT_PULLDOWN);
  digitalWrite(PIN_SR04_TRIG, LOW);
}

void sensor_task(void* /*arg*/) {
  int below_count = 0;
  int above_count = 0;
  bool in_passage = false;             // true between detect-edge and clear-edge
  uint32_t passage_started_ms = 0;
  int trigger_distance_cm = 0;
  uint32_t no_echo_ms = 0;

  for (;;) {
    vTaskDelay(pdMS_TO_TICKS(SENSOR_POLL_INTERVAL_MS));
    int cm = sensor_read_filtered_cm();
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

    // Raw last sample for the LCD icon (refresh ~5 Hz, no debounce).
    // FSM events below use the debounced edges.
    s_obstacle_present = (cm > 0 && cm < SENSOR_TRIGGER_CM);

    if (cm < SENSOR_TRIGGER_CM) {
      below_count++;
      above_count = 0;
      // Detect-edge: obstacle just appeared in the beam (debounced).
      if (!in_passage && below_count >= SENSOR_DEBOUNCE_COUNT) {
        in_passage = true;
        passage_started_ms = now;
        trigger_distance_cm = cm;
        event_t e = {};
        e.src = SRC_SENSOR;
        e.kind = EV_PASSAGE_DETECTED;
        e.i1 = trigger_distance_cm;
        e.i2 = 0;                      // duration unknown at detect-edge
        if (xQueueSend(g_event_q, &e, 0) != pdTRUE) {
          LOGW("evt", "queue full, dropping passage");
        }
      }
    } else {
      above_count++;
      below_count = 0;
      // Clear-edge: obstacle left the beam (debounced).
      if (in_passage && above_count >= SENSOR_DEBOUNCE_COUNT) {
        in_passage = false;
        event_t e = {};
        e.src = SRC_SENSOR;
        e.kind = EV_OBSTACLE_CLEARED;
        e.i1 = trigger_distance_cm;
        e.i2 = (int32_t)(now - passage_started_ms);
        if (xQueueSend(g_event_q, &e, 0) != pdTRUE) {
          LOGW("evt", "queue full, dropping clear");
        }
      }
    }
  }
}

bool sensor_is_obstacle() { return s_obstacle_present; }
