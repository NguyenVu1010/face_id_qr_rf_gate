#pragma once

// === Pin assignments (mirror architecture spec §5) ===
#define PIN_LED_STATUS   2
#define PIN_RC522_CS     5
#define PIN_RC522_SCK    18
#define PIN_RC522_MISO   19
#define PIN_RC522_MOSI   23
#define PIN_RC522_RST    17
#define PIN_RC522_IRQ    16
#define PIN_LCD_SDA      21
#define PIN_LCD_SCL      22
#define PIN_SR04_TRIG    27
#define PIN_SR04_ECHO    26
#define PIN_SERVO        13
#define PIN_BUZZER       14

// === Timings (ms) ===
#define DEFAULT_OPEN_REACHED_MS    300
#define DEFAULT_CLOSE_REACHED_MS   300
#define DEFAULT_PASSAGE_TIMEOUT_MS 10000
#define DEFAULT_WARN_GIVEUP_MS     5000
#define HEARTBEAT_INTERVAL_MS      10000
#define RFID_POLL_INTERVAL_MS      50
#define SENSOR_POLL_INTERVAL_MS    50
#define SENSOR_DEBOUNCE_COUNT      3
#define SENSOR_TRIGGER_CM          25

// === Servo angles ===
#define DEFAULT_SERVO_OPEN_DEG     100
#define DEFAULT_SERVO_CLOSE_DEG    10

// === LCD ===
#define LCD_I2C_ADDR              0x27
#define LCD_COLS                  20
#define LCD_ROWS                  4

// === NVS ===
#define NVS_NS_ALLOWLIST          "allowlist"
#define NVS_NS_CONFIG             "config"
#define NVS_INDEX_KEY             "_index"
#define ALLOWLIST_MAX_ENTRIES     100

// === UART / JSON ===
#define UART_BAUD                 115200
#define UART_LINE_MAX             512
#define JSON_DOC_CAPACITY         768
#define EVENT_QUEUE_LEN           16
#define OUTBOUND_QUEUE_LEN        16
