#include <Arduino.h>
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/timers.h"

// Placeholder queue + timer handles — real definitions land in Task 9.
QueueHandle_t g_event_q = nullptr;
QueueHandle_t g_outbound_q = nullptr;
TimerHandle_t g_open_reached_timer    = nullptr;
TimerHandle_t g_passage_timeout_timer = nullptr;
TimerHandle_t g_warn_giveup_timer     = nullptr;
TimerHandle_t g_close_reached_timer   = nullptr;
TimerHandle_t g_heartbeat_timer       = nullptr;

void setup() {
  Serial.begin(115200);
  delay(50);
  Serial.println("smart_gate firmware boot (stub)");
}

void loop() {
  delay(1000);
}
