#pragma once

#include <stdint.h>

void lcd_init();
void lcd_show_idle();
void lcd_show_opening();
void lcd_show_name(const char* name);
void lcd_show_warn();
void lcd_show_denied();
void lcd_show_closing();

// Presence-icon overlay on row 0 cols 18-19 (writes only on state change).
void lcd_update_icons(bool obstacle_present, bool card_present);

// Last I²C transmission status (used by Task 1.10 diagnostic log).
int  lcd_drv_last_i2c_err();
