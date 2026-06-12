#pragma once
#include <stdint.h>
#include "config.h"

enum EventSrc : uint8_t { SRC_UART, SRC_RFID, SRC_SENSOR, SRC_TIMER };

enum EventKind : uint8_t {
  // Commands from Pi
  EV_CMD_OPEN, EV_CMD_CLOSE, EV_CMD_ADD_UID, EV_CMD_REMOVE_UID,
  EV_CMD_LIST_UIDS, EV_CMD_CONFIG, EV_CMD_STATUS, EV_CMD_PING,
  // Producer events
  EV_RFID_SCAN,          // i1 = granted? (0/1); uid set; name set if granted
  EV_PASSAGE_DETECTED,   // i1 = distance_cm at trigger, i2 = duration_ms in beam
  EV_OBSTACLE_CLEARED,   // sensor: obstacle was below-threshold, now above
  // Timer events (one-shot)
  EV_T_OPEN_REACHED, EV_T_PASSAGE_TIMEOUT, EV_T_WARN_GIVEUP, EV_T_CLOSE_REACHED,
  EV_T_LCD_RESTORE,     // one-shot timer fired: restore LCD to idle if FSM in S_IDLE
  EV_T_LCD_ICON_TICK,   // 200 ms periodic — refresh top-right LCD icons
  EV_T_OBSTACLE_WARN_FIRED, // timer: obstacle persisted 5s; start warn buzzer
};

struct event_t {
  EventSrc  src;
  EventKind kind;
  uint32_t  cmd_id;          // ack correlation; 0 if N/A
  char      uid[16];         // RFID UID hex or cmd payload. Sized for ISO 14443-A (max 7-byte UID = 14 hex chars + NUL).
  char      name[32];        // add_uid name or RFID matched name
  int32_t   i1, i2, i3;      // generic ints; INT32_MIN sentinel = "unset" for cmd_config
};

struct outbound_msg_t {
  char json[UART_LINE_MAX];  // pre-serialized JSON object, NUL-terminated. uart_link appends '\n' at TX time.
};
