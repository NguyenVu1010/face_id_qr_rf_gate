#pragma once

void sensor_init();
void sensor_task(void* arg);

// Raw obstacle presence (last 5 Hz sample, no FSM debounce). Used for LCD icon.
bool sensor_is_obstacle();
