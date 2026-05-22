#include <Arduino.h>

void setup() {
  Serial.begin(115200);
  delay(50);
  Serial.println("smart_gate firmware boot (stub)");
}

void loop() {
  delay(1000);
}

extern "C" void outbound_post(const struct outbound_msg_t*) { /* stub, removed in Task 5 */ }
