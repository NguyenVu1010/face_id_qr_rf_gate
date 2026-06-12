#include "lcd_drv.h"
#include "../include/config.h"
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

static LiquidCrystal_I2C s_lcd(LCD_I2C_ADDR, LCD_COLS, LCD_ROWS);

static void write_row(int row, const char* text) {
  s_lcd.setCursor(0, row);
  // Pad/truncate to LCD_COLS
  char buf[LCD_COLS + 1];
  size_t n = strlen(text);
  for (int i = 0; i < LCD_COLS; ++i) {
    buf[i] = (size_t)i < n ? text[i] : ' ';
  }
  buf[LCD_COLS] = '\0';
  s_lcd.print(buf);
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
  lcd_show_idle();
}

void lcd_show_idle() {
  s_lcd.clear();
  write_row(0, "smart_gate ready");
  write_row(1, "Tap RFID or wait");
  write_row(2, "for face auth");
  write_row(3, "");
}

void lcd_show_opening() {
  s_lcd.clear();
  write_row(0, "Opening gate...");
}

void lcd_show_name(const char* name) {
  s_lcd.clear();
  write_row(0, "Welcome:");
  write_row(1, name);
}

void lcd_show_warn() {
  s_lcd.clear();
  write_row(0, "Please pass thru");
  write_row(1, "or gate closes");
}

void lcd_show_denied() {
  s_lcd.clear();
  write_row(0, "Access denied");
}

void lcd_show_closing() {
  s_lcd.clear();
  write_row(0, "Closing...");
}
