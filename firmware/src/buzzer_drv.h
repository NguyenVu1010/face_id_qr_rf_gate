#pragma once

void buzzer_init();
void buzzer_beep_ok();              // single 80ms beep
void buzzer_beep_err();             // 3× 60ms beeps
void buzzer_start_warn_pattern();   // toggling pattern via software timer
void buzzer_stop_warn_pattern();
