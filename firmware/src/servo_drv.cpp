#include "servo_drv.h"
#include "../include/config.h"
#include <Arduino.h>
#include <ESP32Servo.h>
#include "freertos/FreeRTOS.h"
#include "freertos/timers.h"

static Servo s_servo;
static int s_open_deg  = DEFAULT_SERVO_OPEN_DEG;
static int s_close_deg = DEFAULT_SERVO_CLOSE_DEG;
static TimerHandle_t s_detach_timer = nullptr;

static void cb_detach(TimerHandle_t) {
  // Release PWM and drive the line LOW so the SG90 coil stops drawing idle
  // current (~6 mA hum + heat). Next servo_command_async() re-attaches.
  if (s_servo.attached()) s_servo.detach();
  digitalWrite(PIN_SERVO, LOW);
}

void servo_init() {
  pinMode(PIN_SERVO, OUTPUT);
  digitalWrite(PIN_SERVO, LOW);
  s_servo.setPeriodHertz(50);
  s_servo.attach(PIN_SERVO, 500, 2400);  // typical SG90 pulse range µs
  s_servo.write(s_close_deg);
  // Detach timer is one-shot; period is rewritten on each command via
  // xTimerChangePeriod() so the 1000 ms placeholder here is irrelevant.
  s_detach_timer = xTimerCreate("svDet", pdMS_TO_TICKS(1000),
                                pdFALSE, nullptr, cb_detach);
}

void servo_set_angles(int open_deg, int close_deg) {
  // Clamp to physical safe range — protects against a bad cmd:config (e.g.
  // servo_open_deg=180) driving the horn into the enclosure wall and
  // stalling SG90 at ~700 mA until brown-out.
  s_open_deg  = constrain(open_deg,  SERVO_MIN_PHYS_DEG, SERVO_MAX_PHYS_DEG);
  s_close_deg = constrain(close_deg, SERVO_MIN_PHYS_DEG, SERVO_MAX_PHYS_DEG);
}

void servo_open()  { s_servo.write(s_open_deg); }
void servo_close() { s_servo.write(s_close_deg); }
int  servo_open_deg()  { return s_open_deg; }
int  servo_close_deg() { return s_close_deg; }

void servo_command_async(int target_deg, int expected_travel_ms) {
  target_deg = constrain(target_deg, SERVO_MIN_PHYS_DEG, SERVO_MAX_PHYS_DEG);
  if (!s_servo.attached()) {
    s_servo.attach(PIN_SERVO, 500, 2400);
  }
  s_servo.write(target_deg);
  if (s_detach_timer) {
    xTimerChangePeriod(s_detach_timer,
                       pdMS_TO_TICKS(expected_travel_ms + 200), 0);
    xTimerStart(s_detach_timer, 0);
  }
}
