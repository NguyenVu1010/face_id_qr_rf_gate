#pragma once
#include <Arduino.h>

void buzzer_init();
void buzzer_beep_ok();          // deprecated — blocking, kept for old callers
void buzzer_beep_err();         // deprecated — blocking
void buzzer_beep_ok_async();    // schedule non-blocking 80ms HIGH→LOW pulse
void buzzer_beep_err_async();   // schedule non-blocking 3× 60ms HIGH/LOW pattern (~360 ms total)
void buzzer_start_warn_pattern();   // existing
void buzzer_stop_warn_pattern();    // existing
