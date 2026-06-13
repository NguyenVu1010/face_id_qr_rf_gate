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

static volatile bool     s_card_present = false;
static volatile uint32_t s_card_last_ms = 0;

// Health monitor state
static bool     s_rfid_ok            = false;
static uint32_t s_last_probe_ms      = 0;
static uint32_t s_last_fault_emit_ms = 0;

// Per-UID rate limit
static char     s_last_uid[24]   = {0};
static uint32_t s_last_uid_ms    = 0;

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
  delay(50);
  uint8_t ver = s_rc522.PCD_ReadRegister(MFRC522::VersionReg);
  if (ver != 0x91 && ver != 0x92) {
    LOGE("rfid", "init failed version=0x%02x", ver);
    s_rfid_ok = false;
    return;
  }
  s_rfid_ok = true;
  LOGI("rfid", "init ok version=0x%02x", ver);
}

void rfid_task(void* /*arg*/) {
  for (;;) {
    vTaskDelay(pdMS_TO_TICKS(RFID_POLL_INTERVAL_MS));

    // Drop the icon flag if no card has been seen for >300 ms.
    if (s_card_present && (millis() - s_card_last_ms) > 300) {
      s_card_present = false;
    }

    // ---- Fault path: try recovery every 60 s ----
    if (!s_rfid_ok) {
      if (millis() - s_last_probe_ms > 60000) {
        s_last_probe_ms = millis();
        s_rc522.PCD_Reset();
        delay(50);
        s_rc522.PCD_Init();
        delay(50);
        uint8_t ver = s_rc522.PCD_ReadRegister(MFRC522::VersionReg);
        if (ver == 0x91 || ver == 0x92) {
          LOGI("rfid", "recovered version=0x%02x", ver);
          s_rfid_ok = true;
        } else if (millis() - s_last_fault_emit_ms > 300000) {
          s_last_fault_emit_ms = millis();
          LOGW("rfid", "rfid_fault no response ver=0x%02x", ver);
        }
      }
      continue;
    }

    // ---- Healthy path: periodic version drift probe (60 s) ----
    if (millis() - s_last_probe_ms > 60000) {
      s_last_probe_ms = millis();
      uint8_t ver = s_rc522.PCD_ReadRegister(MFRC522::VersionReg);
      if (ver != 0x91 && ver != 0x92) {
        LOGW("rfid", "drift version=0x%02x, will recover next cycle", ver);
        s_rfid_ok = false;
        continue;
      }
    }

    if (!s_rc522.PICC_IsNewCardPresent()) continue;

    // Card detected this poll — refresh the icon hold window.
    s_card_present = true;
    s_card_last_ms = millis();

    if (!s_rc522.PICC_ReadCardSerial()) continue;

    char uid_hex[16];
    uid_to_hex(s_rc522.uid, uid_hex, sizeof uid_hex);

    // Per-UID rate limit: same UID within 1 s → skip silently.
    if (strcmp(uid_hex, s_last_uid) == 0 && (millis() - s_last_uid_ms) < 1000) {
      s_rc522.PICC_HaltA();
      s_rc522.PCD_StopCrypto1();
      continue;
    }
    strncpy(s_last_uid, uid_hex, sizeof s_last_uid - 1);
    s_last_uid[sizeof s_last_uid - 1] = '\0';
    s_last_uid_ms = millis();

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

bool rfid_is_card_present() { return s_card_present; }
