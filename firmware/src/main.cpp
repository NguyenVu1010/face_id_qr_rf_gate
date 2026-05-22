#include <Arduino.h>
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

// Placeholder queue handles — real definitions land in Task 9.
QueueHandle_t g_event_q = nullptr;
QueueHandle_t g_outbound_q = nullptr;

void setup() {
  Serial.begin(115200);
  delay(50);
  Serial.println("smart_gate firmware boot (stub)");
}

void loop() {
  delay(1000);
}
