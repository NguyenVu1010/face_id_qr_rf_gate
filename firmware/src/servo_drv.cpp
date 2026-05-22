#include "servo_drv.h"
#include "../include/config.h"
#include <ESP32Servo.h>

static Servo s_servo;
static int s_open_deg  = DEFAULT_SERVO_OPEN_DEG;
static int s_close_deg = DEFAULT_SERVO_CLOSE_DEG;

void servo_init() {
  s_servo.setPeriodHertz(50);
  s_servo.attach(PIN_SERVO, 500, 2400);  // typical SG90 pulse range µs
  s_servo.write(s_close_deg);
}

void servo_set_angles(int open_deg, int close_deg) {
  if (open_deg  >= 0 && open_deg  <= 180) s_open_deg  = open_deg;
  if (close_deg >= 0 && close_deg <= 180) s_close_deg = close_deg;
}

void servo_open()  { s_servo.write(s_open_deg); }
void servo_close() { s_servo.write(s_close_deg); }
int  servo_open_deg()  { return s_open_deg; }
int  servo_close_deg() { return s_close_deg; }
