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
