#pragma once

void servo_init();
void servo_set_angles(int open_deg, int close_deg);  // runtime override; persisted by caller
void servo_open();
void servo_close();
int  servo_open_deg();
int  servo_close_deg();

// Async command: attach (if needed), write target, then arm a one-shot timer
// that detaches and drives PIN_SERVO LOW after expected_travel_ms + 200 ms
// margin. Eliminates the SG90 idle hum + coil heat between commands.
void servo_command_async(int target_deg, int expected_travel_ms);
