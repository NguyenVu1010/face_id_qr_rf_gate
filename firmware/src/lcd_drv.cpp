#include "lcd_drv.h"
#include "../include/config.h"
#include "log.h"
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

static LiquidCrystal_I2C s_lcd(LCD_I2C_ADDR, LCD_COLS, LCD_ROWS);

// Row 0 cols 18-19 are reserved for presence icons (top-right on 20-col LCD);
// text writes on row 0 must stay within ROW0_TEXT_COLS to avoid stomping the
// icon cells.
#ifndef ROW0_TEXT_COLS
#define ROW0_TEXT_COLS 18
#endif

// Obstacle warning glyph — stylised warning triangle with centre dot
// (5 cols × 8 rows; 26/40 ≈ 65% pixel fill, clearly recognisable on the
// deployed module)
static const uint8_t GLYPH_OBSTACLE[8] = {
    0b00100,
    0b01110,
    0b01110,
    0b11111,
    0b11011,
    0b11111,
    0b11111,
    0b00000,
};

// RFID card glyph — two concentric arcs above a solid card body
// (24/40 = 60% pixel fill)
static const uint8_t GLYPH_RFID[8] = {
    0b00100,
    0b01110,
    0b11011,
    0b00100,
    0b11111,
    0b11111,
    0b11111,
    0b00000,
};

static int s_last_i2c_err = 0;

// Task 3.14: probe-before-write + bit-bang recovery for stuck PCF8574 I²C bus.
//
// The PCF8574 backpack on the LCD can latch SDA low after ESD or power glitch.
// LiquidCrystal_I2C::print() then blocks inside Wire.endTransmission() until
// the task watchdog fires, which resets the gate mid-passage. We address this
// by probing the bus before every write; on NACK we bit-bang 9 SCL pulses +
// manual STOP to release any stuck slave, re-init Wire + the LCD, then retry
// the probe once. If recovery fails we set s_last_i2c_err and skip the write
// so the caller observes the fault via lcd_drv_last_i2c_err() (consumed by the
// per-RFID-swipe diagnostic log from Task 1.10).

static int lcd_probe() {
  Wire.beginTransmission(LCD_I2C_ADDR);
  return Wire.endTransmission();
}

static void i2c_recover_bus() {
  // Detach Wire from the bus and bit-bang SCL for 9 clocks + manual STOP.
  // PCF8574 has no reset pin so this is the only way to free a wedged slave.
  pinMode(PIN_LCD_SDA, OUTPUT);
  pinMode(PIN_LCD_SCL, OUTPUT);
  digitalWrite(PIN_LCD_SDA, HIGH);
  digitalWrite(PIN_LCD_SCL, HIGH);
  delayMicroseconds(10);

  // 9 SCL pulses — enough for any in-flight byte + ACK bit to clock through
  // so the stuck slave releases SDA.
  for (int i = 0; i < 9; i++) {
    digitalWrite(PIN_LCD_SCL, LOW);  delayMicroseconds(5);
    digitalWrite(PIN_LCD_SCL, HIGH); delayMicroseconds(5);
  }

  // Manual STOP condition: SDA low → SDA high while SCL is high.
  digitalWrite(PIN_LCD_SDA, LOW);  delayMicroseconds(5);
  digitalWrite(PIN_LCD_SCL, LOW);  delayMicroseconds(5);
  digitalWrite(PIN_LCD_SCL, HIGH); delayMicroseconds(5);
  digitalWrite(PIN_LCD_SDA, HIGH); delayMicroseconds(5);

  // Re-hand the pins to the Wire peripheral and re-init the LCD controller +
  // re-register the custom glyphs (RAM in the HD44780 is volatile across the
  // soft re-init, so we have to re-upload them).
  Wire.begin(PIN_LCD_SDA, PIN_LCD_SCL);
  s_lcd.init();
  s_lcd.backlight();
  s_lcd.createChar(0, (uint8_t*)GLYPH_OBSTACLE);
  s_lcd.createChar(1, (uint8_t*)GLYPH_RFID);
}

static bool lcd_ensure_bus_ok() {
  int rc = lcd_probe();
  if (rc == 0) return true;
  LOGW("lcd", "i2c bus stuck rc=%d, attempting recovery", rc);
  i2c_recover_bus();
  rc = lcd_probe();
  if (rc != 0) {
    s_last_i2c_err = rc;
    LOGW("lcd", "i2c recovery failed rc=%d, skipping write", rc);
    return false;
  }
  LOGI("lcd", "i2c bus recovered");
  return true;
}

static void write_row(int row, const char* text, int width) {
  s_lcd.setCursor(0, row);
  // Pad/truncate to `width` chars.
  char buf[LCD_COLS + 1];
  if (width > LCD_COLS) width = LCD_COLS;
  size_t n = strlen(text);
  for (int i = 0; i < width; ++i) {
    buf[i] = (size_t)i < n ? text[i] : ' ';
  }
  buf[width] = '\0';
  s_lcd.print(buf);

  // Probe bus health after write — single addressing transaction. Captures
  // whether the LCD still ACKs its address after the write burst. Does not
  // directly report write success, but a NACK here indicates a stuck bus or
  // missing device. Pre-write probe + recovery added in Task 3.14 via
  // lcd_ensure_bus_ok() at each lcd_show_* entry.
  s_last_i2c_err = lcd_probe();
}

static void write_row(int row, const char* text) {
  write_row(row, text, LCD_COLS);
}

void lcd_init() {
  // LiquidCrystal_I2C::init() internally calls Wire.begin() with no args, which
  // emits a "[W] Wire.cpp begin(): Bus already started in Master Mode" warning
  // because we initialise the bus explicitly here first with our pin assignment.
  // The warning is harmless — the library's second begin() is a no-op once
  // i2cIsInit() returns true. Avoiding the warning via Wire.setPins() instead
  // of Wire.begin() caused intermittent boot crashes during LCD command init
  // (s_lcd.begin internals) on this arduino-esp32 2.0.x build, so we keep the
  // explicit begin and tolerate the cosmetic warning.
  Wire.begin(PIN_LCD_SDA, PIN_LCD_SCL);
  s_lcd.init();
  s_lcd.backlight();
  s_lcd.createChar(0, (uint8_t*)GLYPH_OBSTACLE);
  s_lcd.createChar(1, (uint8_t*)GLYPH_RFID);
  lcd_show_idle();
}

void lcd_show_idle() {
  if (!lcd_ensure_bus_ok()) return;
  s_lcd.clear();
  write_row(0, "smart_gate ready", ROW0_TEXT_COLS);
  write_row(1, "Tap RFID or wait");
  write_row(2, "for face auth");
  write_row(3, "");
}

void lcd_show_opening() {
  if (!lcd_ensure_bus_ok()) return;
  s_lcd.clear();
  write_row(0, "Opening gate...", ROW0_TEXT_COLS);
}

void lcd_show_name(const char* name) {
  if (!lcd_ensure_bus_ok()) return;
  s_lcd.clear();
  write_row(0, "Welcome:", ROW0_TEXT_COLS);
  // Name goes on row 1 (full width); row 0 already shrunk to 18 cols for icons.
  write_row(1, name);
}

void lcd_show_warn() {
  if (!lcd_ensure_bus_ok()) return;
  s_lcd.clear();
  write_row(0, "Please pass thru", ROW0_TEXT_COLS);
  write_row(1, "or gate closes");
}

void lcd_show_denied() {
  if (!lcd_ensure_bus_ok()) return;
  s_lcd.clear();
  write_row(0, "Access denied", ROW0_TEXT_COLS);
}

void lcd_show_closing() {
  if (!lcd_ensure_bus_ok()) return;
  s_lcd.clear();
  write_row(0, "Closing...", ROW0_TEXT_COLS);
}

void lcd_show_recovery() {
  if (!lcd_ensure_bus_ok()) return;
  s_lcd.clear();
  write_row(0, "Recovery", ROW0_TEXT_COLS);
  write_row(1, "verify clear");
}

void lcd_update_icons(bool obstacle_present, bool card_present) {
  static bool s_last_obs = false;
  static bool s_last_rfid = false;
  static bool s_first = true;

  if (!s_first && obstacle_present == s_last_obs && card_present == s_last_rfid) {
    return;   // no I²C write when state unchanged
  }
  if (!lcd_ensure_bus_ok()) return;
  s_first = false;
  s_last_obs = obstacle_present;
  s_last_rfid = card_present;

  s_lcd.setCursor(18, 0);
  s_lcd.write(obstacle_present ? (uint8_t)0 : ' ');
  s_lcd.setCursor(19, 0);
  s_lcd.write(card_present ? (uint8_t)1 : ' ');

  // Post-write probe — same single-transaction probe as write_row, for
  // consistency across all LCD write paths (Task 1.10).
  s_last_i2c_err = lcd_probe();
}

int lcd_drv_last_i2c_err() { return s_last_i2c_err; }
