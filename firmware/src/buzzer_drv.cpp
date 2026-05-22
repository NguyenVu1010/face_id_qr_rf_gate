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
