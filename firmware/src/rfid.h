#pragma once

void rfid_init();
void rfid_task(void* arg);

// True for ~300 ms after the last successful PICC_IsNewCardPresent().
// Used by the LCD icon overlay; the FSM still receives one EV_RFID_SCAN per
// debounced scan.
bool rfid_is_card_present();
