#include "lcd_drv.h"
#include "../include/config.h"
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
  s_lcd.clear();
  write_row(0, "smart_gate ready", ROW0_TEXT_COLS);
  write_row(1, "Tap RFID or wait");
  write_row(2, "for face auth");
  write_row(3, "");
}

void lcd_show_opening() {
  s_lcd.clear();
  write_row(0, "Opening gate...", ROW0_TEXT_COLS);
}

void lcd_show_name(const char* name) {
  s_lcd.clear();
  write_row(0, "Welcome:", ROW0_TEXT_COLS);
  // Name goes on row 1 (full width); row 0 already shrunk to 18 cols for icons.
  write_row(1, name);
}

void lcd_show_warn() {
  s_lcd.clear();
  write_row(0, "Please pass thru", ROW0_TEXT_COLS);
  write_row(1, "or gate closes");
}

void lcd_show_denied() {
  s_lcd.clear();
  write_row(0, "Access denied", ROW0_TEXT_COLS);
}

void lcd_show_closing() {
  s_lcd.clear();
  write_row(0, "Closing...", ROW0_TEXT_COLS);
}

void lcd_update_icons(bool obstacle_present, bool card_present) {
  static bool s_last_obs = false;
  static bool s_last_rfid = false;
  static bool s_first = true;

  if (!s_first && obstacle_present == s_last_obs && card_present == s_last_rfid) {
    return;   // no I²C write when state unchanged
  }
  s_first = false;
  s_last_obs = obstacle_present;
  s_last_rfid = card_present;

  s_lcd.setCursor(18, 0);
  s_lcd.write(obstacle_present ? (uint8_t)0 : ' ');
  s_lcd.setCursor(19, 0);
  s_lcd.write(card_present ? (uint8_t)1 : ' ');

  // capture transmission status for the I²C diagnostic log (Task 1.10)
  s_last_i2c_err = 0;   // refined in Task 3.14 with real probe
}

int lcd_drv_last_i2c_err() { return s_last_i2c_err; }
