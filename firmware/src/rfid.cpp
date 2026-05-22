#include "rfid.h"
#include "../include/config.h"
#include "../include/events.h"
#include "../include/log.h"
#include "uart_link.h"
#include "allowlist.h"
#include <SPI.h>
#include <MFRC522.h>
#include <string.h>

static MFRC522 s_rc522(PIN_RC522_CS, PIN_RC522_RST);

static void uid_to_hex(const MFRC522::Uid& uid, char* out, size_t out_n) {
  size_t pos = 0;
  for (byte i = 0; i < uid.size && pos + 2 < out_n; ++i) {
    snprintf(out + pos, out_n - pos, "%02x", uid.uidByte[i]);
    pos += 2;
  }
  if (pos < out_n) out[pos] = '\0';
}

void rfid_init() {
  SPI.begin(PIN_RC522_SCK, PIN_RC522_MISO, PIN_RC522_MOSI, PIN_RC522_CS);
  s_rc522.PCD_Init();
}

void rfid_task(void* /*arg*/) {
  for (;;) {
    vTaskDelay(pdMS_TO_TICKS(RFID_POLL_INTERVAL_MS));
    if (!s_rc522.PICC_IsNewCardPresent()) continue;
    if (!s_rc522.PICC_ReadCardSerial()) continue;

    char uid_hex[16];
    uid_to_hex(s_rc522.uid, uid_hex, sizeof uid_hex);

    event_t e = {};
    e.src = SRC_RFID;
    e.kind = EV_RFID_SCAN;
    strncpy(e.uid, uid_hex, sizeof e.uid - 1);

    char name[32] = {0};
    bool granted = allowlist_lookup(uid_hex, name, sizeof name);
    e.i1 = granted ? 1 : 0;
    if (granted) strncpy(e.name, name, sizeof e.name - 1);

    if (xQueueSend(g_event_q, &e, 0) != pdTRUE) {
      LOGW("evt", "queue full, dropping rfid scan uid=%s", uid_hex);
    }

    s_rc522.PICC_HaltA();
    s_rc522.PCD_StopCrypto1();
  }
}
