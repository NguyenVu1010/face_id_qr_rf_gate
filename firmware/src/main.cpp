#include <Arduino.h>
#include <esp_task_wdt.h>
#include <esp_system.h>
#include <esp_heap_caps.h>
#include <ArduinoJson.h>
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/timers.h"

#include "../include/config.h"
#include "../include/events.h"
#include "../include/version.h"
#include "../include/log.h"

#include "uart_link.h"
#include "rfid.h"
#include "sensor.h"
#include "gate_fsm.h"
#include "servo_drv.h"
#include "lcd_drv.h"
#include "buzzer_drv.h"
#include "allowlist.h"

// === Global queues + timers (extern'd in module headers) ===
QueueHandle_t g_event_q    = nullptr;
QueueHandle_t g_outbound_q = nullptr;
TimerHandle_t g_open_reached_timer    = nullptr;
TimerHandle_t g_passage_timeout_timer = nullptr;
TimerHandle_t g_warn_giveup_timer     = nullptr;
TimerHandle_t g_close_reached_timer   = nullptr;
TimerHandle_t g_heartbeat_timer       = nullptr;

static const char* reset_reason_string() {
  switch (esp_reset_reason()) {
    case ESP_RST_POWERON:  return "power_on";
    case ESP_RST_SW:       return "sw_reset";
    case ESP_RST_PANIC:    return "panic";
    case ESP_RST_INT_WDT:  return "watchdog";
    case ESP_RST_TASK_WDT: return "watchdog";
    case ESP_RST_WDT:      return "watchdog";
    case ESP_RST_BROWNOUT: return "brownout";
    default:               return "other";
  }
}

static void emit_boot_event() {
  JsonDocument doc;
  doc["type"] = "evt";
  doc["v"]    = "boot";
  doc["data"]["fw"]            = FW_VERSION;
  doc["data"]["free_heap"]     = (uint32_t)esp_get_free_heap_size();
  doc["data"]["reset_reason"]  = reset_reason_string();
  outbound_msg_t out;
  size_t w = serializeJson(doc, out.json, sizeof out.json);
  if (w > 0 && w < sizeof out.json) outbound_send(out);
}

void setup() {
  // 1. Status LED
  pinMode(PIN_LED_STATUS, OUTPUT);
  digitalWrite(PIN_LED_STATUS, LOW);

  // 2. UARTs up early (so logs work).
  //    Serial  (UART0, GPIO 1/3, USB-CDC) → `pio device monitor` debug + ESP_LOG sink.
  //    Serial1 (UART1, GPIO 32/25)        → Pi app comm; configured inside uart_link_init().
  Serial.begin(UART_BAUD);
  uart_link_init();

  // 3. NVS / allowlist
  allowlist_init();

  // 4. Peripheral init
  servo_init();
  lcd_init();
  buzzer_init();
  rfid_init();
  sensor_init();

  // 5. Queues
  g_event_q    = xQueueCreate(EVENT_QUEUE_LEN,    sizeof(event_t));
  g_outbound_q = xQueueCreate(OUTBOUND_QUEUE_LEN, sizeof(outbound_msg_t));
  if (!g_event_q || !g_outbound_q) {
    ESP_LOGE("main", "queue alloc failed");
    while (1) vTaskDelay(pdMS_TO_TICKS(1000));
  }

  // 6. Timers
  g_open_reached_timer    = xTimerCreate("openR", pdMS_TO_TICKS(DEFAULT_OPEN_REACHED_MS),   pdFALSE, nullptr, cb_open_reached);
  g_passage_timeout_timer = xTimerCreate("passT", pdMS_TO_TICKS(DEFAULT_PASSAGE_TIMEOUT_MS),pdFALSE, nullptr, cb_passage_timeout);
  g_warn_giveup_timer     = xTimerCreate("warnG", pdMS_TO_TICKS(DEFAULT_WARN_GIVEUP_MS),    pdFALSE, nullptr, cb_warn_giveup);
  g_close_reached_timer   = xTimerCreate("closeR",pdMS_TO_TICKS(DEFAULT_CLOSE_REACHED_MS),  pdFALSE, nullptr, cb_close_reached);
  g_heartbeat_timer       = xTimerCreate("hb",    pdMS_TO_TICKS(HEARTBEAT_INTERVAL_MS),     pdTRUE,  nullptr, cb_heartbeat);

  // 7. FSM init (loads NVS config, applies servo angles)
  gate_fsm_init();

  // 8. Task watchdog: 8s timeout, panic on expiry
  // Using 2-arg form: IDF bundled with arduino-esp32 3.x / platform=espressif32@^6 uses
  // esp_task_wdt_init(uint32_t timeout_seconds, bool panic) — not the IDF 5.x struct form.
  esp_task_wdt_init(8, true);

  // 9. Spawn tasks
  xTaskCreatePinnedToCore(uart_link_task,  "uart_link",  4096, nullptr, 3, nullptr, 0);
  xTaskCreatePinnedToCore(rfid_task,       "rfid",       3072, nullptr, 2, nullptr, 1);
  xTaskCreatePinnedToCore(sensor_task,     "sensor",     2048, nullptr, 2, nullptr, 1);
  xTaskCreatePinnedToCore(gate_fsm_task,   "gate_fsm",   4096, nullptr, 4, nullptr, 1);

  // 10. Start heartbeat
  xTimerStart(g_heartbeat_timer, 0);

  // 11. Boot event
  emit_boot_event();
  digitalWrite(PIN_LED_STATUS, HIGH);
}

void loop() {
  // All work is in FreeRTOS tasks.
  vTaskDelay(pdMS_TO_TICKS(1000));
}
