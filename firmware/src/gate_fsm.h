#pragma once
#include "freertos/FreeRTOS.h"
#include "freertos/timers.h"
#include "../include/events.h"

enum GateState { S_IDLE, S_OPENING, S_OPEN_WAIT, S_TIMEOUT_WARN, S_CLOSING };

// Globals owned by main.cpp:
extern TimerHandle_t g_open_reached_timer;
extern TimerHandle_t g_passage_timeout_timer;
extern TimerHandle_t g_warn_giveup_timer;
extern TimerHandle_t g_close_reached_timer;
extern TimerHandle_t g_heartbeat_timer;

void gate_fsm_init();
void gate_fsm_task(void* arg);

// Timer callbacks (used by main.cpp's xTimerCreate calls):
void cb_open_reached(TimerHandle_t);
void cb_passage_timeout(TimerHandle_t);
void cb_warn_giveup(TimerHandle_t);
void cb_close_reached(TimerHandle_t);
void cb_heartbeat(TimerHandle_t);
