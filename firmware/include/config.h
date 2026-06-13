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

// Pi link runs on ESP32 UART1 routed via the GPIO matrix (decision #26, 2026-05-23).
// Pi pin 8 (BCM14, TX0) → ESP32 GPIO 32 (UART1 RX);
// Pi pin 10 (BCM15, RX0) ← ESP32 GPIO 25 (UART1 TX).
// UART0 (GPIO 1/3, USB-CDC) stays reserved for `pio device monitor` debug + `esptool.py` flashing.
#define PIN_PI_UART_RX   32
#define PIN_PI_UART_TX   25

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
// Physical safe range for SG90 horn vs enclosure — protects against a bad
// cmd:config (e.g. servo_open_deg=180) driving the horn into the wall and
// stalling the motor at ~700 mA until brown-out.
#define SERVO_MIN_PHYS_DEG         5
#define SERVO_MAX_PHYS_DEG         110
// Expected servo travel time end-to-end. Used both for the async detach timer
// margin and as the base period for the stall watchdog (2× this value).
// Kept aligned with DEFAULT_OPEN_REACHED_MS / DEFAULT_CLOSE_REACHED_MS so the
// reached-event and stall windows stay consistent.
#define SERVO_EXPECTED_TRAVEL_MS   DEFAULT_OPEN_REACHED_MS

// === LCD ===
#define LCD_I2C_ADDR              0x27
#define LCD_COLS                  20
#define LCD_ROWS                  4

// === NVS ===
#define NVS_NS_ALLOWLIST          "allowlist"
#define NVS_NS_CONFIG             "config"
#define NVS_NS_GATE_STATE         "gate_state"
#define NVS_INDEX_KEY             "_index"
#define ALLOWLIST_MAX_ENTRIES     100

// === Brown-out recovery ===
// Hold servo at 90° neutral for this long before falling through to enter_idle(),
// giving any person in the doorway time to step clear.
#define RECOVERY_HOLD_MS          5000
#define RECOVERY_NEUTRAL_DEG      90

// === UART / JSON ===
#define UART_BAUD                 115200
#define UART_LINE_MAX             512
#define JSON_DOC_CAPACITY         768
#define EVENT_QUEUE_LEN           16
#define OUTBOUND_QUEUE_LEN        16
