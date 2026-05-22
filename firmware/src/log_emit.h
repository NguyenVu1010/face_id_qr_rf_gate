#pragma once
#include <stdint.h>

// Forward declaration: defined in uart_link.cpp; safe to call before uart_link_init returns
// (early calls are buffered into outbound_q only if it exists; otherwise dropped silently).
struct outbound_msg_t;
extern "C" void outbound_post(const struct outbound_msg_t* m);  // implemented in uart_link.cpp

void emit_log(const char* lvl, const char* tag, const char* fmt, ...);
