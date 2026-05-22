#pragma once
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "../include/events.h"

// Globals owned by main.cpp, declared here for module access:
extern QueueHandle_t g_event_q;
extern QueueHandle_t g_outbound_q;

void uart_link_init();
void uart_link_task(void* arg);

// Helper used by FSM / log_emit to enqueue an outbound JSON Line.
// Returns true if queued, false if queue full (caller decides whether to drop or fallback).
bool outbound_send(const outbound_msg_t& m);
