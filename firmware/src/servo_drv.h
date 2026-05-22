#pragma once

void servo_init();
void servo_set_angles(int open_deg, int close_deg);  // runtime override; persisted by caller
void servo_open();
void servo_close();
int  servo_open_deg();
int  servo_close_deg();
