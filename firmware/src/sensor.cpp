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
