#include "buzzer_drv.h"
#include "../include/config.h"
#include <Arduino.h>
#include "freertos/FreeRTOS.h"
#include "freertos/timers.h"

static TimerHandle_t s_warn_timer = nullptr;
static volatile bool s_warn_state = false;

static TimerHandle_t s_pulse_timer = nullptr;
static int s_pulse_remaining = 0;        // how many state transitions left
static int s_pulse_period_ms = 60;       // 60 ms for err, 80 for ok
static bool s_pulse_high_next = true;    // next state

static void warn_timer_cb(TimerHandle_t) {
  s_warn_state = !s_warn_state;
  digitalWrite(PIN_BUZZER, s_warn_state ? HIGH : LOW);
}

static void cb_pulse(TimerHandle_t) {
  if (s_pulse_remaining <= 0) {
    digitalWrite(PIN_BUZZER, LOW);
    return;
  }
  digitalWrite(PIN_BUZZER, s_pulse_high_next ? HIGH : LOW);
  s_pulse_high_next = !s_pulse_high_next;
  s_pulse_remaining--;
  if (s_pulse_remaining > 0) {
    xTimerChangePeriod(s_pulse_timer, pdMS_TO_TICKS(s_pulse_period_ms), 0);
    xTimerStart(s_pulse_timer, 0);
  } else {
    digitalWrite(PIN_BUZZER, LOW);
  }
}

void buzzer_init() {
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);
  s_warn_timer = xTimerCreate("buzzerWarn", pdMS_TO_TICKS(250), pdTRUE, nullptr, warn_timer_cb);
  s_pulse_timer = xTimerCreate("buzzPulse", pdMS_TO_TICKS(60),
                               pdFALSE, nullptr, cb_pulse);
  // Stop in case re-init while running (idempotent)
  if (s_pulse_timer) xTimerStop(s_pulse_timer, 0);
}

void buzzer_beep_ok_async() {
  if (!s_pulse_timer) return;
  s_pulse_period_ms = 80;
  s_pulse_remaining = 2;    // HIGH then LOW
  s_pulse_high_next = true;
  xTimerChangePeriod(s_pulse_timer, pdMS_TO_TICKS(s_pulse_period_ms), 0);
  xTimerStart(s_pulse_timer, 0);
}

void buzzer_beep_err_async() {
  if (!s_pulse_timer) return;
  s_pulse_period_ms = 60;
  s_pulse_remaining = 6;    // 3× HIGH/LOW (matches original blocking pattern)
  s_pulse_high_next = true;
  xTimerChangePeriod(s_pulse_timer, pdMS_TO_TICKS(s_pulse_period_ms), 0);
  xTimerStart(s_pulse_timer, 0);
}

// Legacy blocking variants — keep as thin wrappers to avoid touching every caller
void buzzer_beep_ok()  { buzzer_beep_ok_async(); }
void buzzer_beep_err() { buzzer_beep_err_async(); }

void buzzer_start_warn_pattern() {
  s_warn_state = false;
  if (s_warn_timer) xTimerStart(s_warn_timer, 0);
}

void buzzer_stop_warn_pattern() {
  if (s_warn_timer) xTimerStop(s_warn_timer, 0);
  digitalWrite(PIN_BUZZER, LOW);
}
