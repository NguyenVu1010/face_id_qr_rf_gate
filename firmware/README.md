# smart_gate ESP32 firmware

Implements the firmware described in [`../docs/superpowers/specs/2026-05-22-esp32-firmware-design.md`](../docs/superpowers/specs/2026-05-22-esp32-firmware-design.md).

Talks JSON Lines over USB-CDC to a Raspberry Pi 5. Operates the gate independently of the Pi if the link is lost; RFID auth is local via NVS allowlist.

## Toolchain

- [PlatformIO](https://platformio.org/) (CLI: `pio`).
- Framework: Arduino-ESP32.
- Board: ESP32-WROOM-32 DevKit.

## Pin map (mirrors architecture spec §5)

| GPIO | Peripheral |
| --- | --- |
| 1   | UART0 TX — `pio device monitor` debug + `esptool.py` flashing only |
| 3   | UART0 RX — `pio device monitor` + `esptool.py` flashing only |
| 2   | Onboard status LED |
| 5   | RC522 CS |
| 18  | RC522 SCK |
| 19  | RC522 MISO |
| 23  | RC522 MOSI |
| 17  | RC522 RST |
| 16  | RC522 IRQ (reserved; polling mode) |
| 21  | LCD I2C SDA |
| 22  | LCD I2C SCL |
| **25**  | **UART1 TX → Pi pin 10 (BCM15, RX0)** — Pi app comm |
| **32**  | **UART1 RX ← Pi pin 8  (BCM14, TX0)** — Pi app comm |
| 27  | HC-SR04 TRIG |
| 26  | HC-SR04 ECHO (via voltage divider) |
| 13  | Servo SG90 PWM |
| 14  | Buzzer (via 2N3904 NPN) |

Runtime Pi↔ESP32 app comm uses the **3-wire GPIO UART link** (decision #26, 2026-05-23): ESP32 GPIO 32/25 ↔ Pi header pins 8/10. USB cable to the DevKit is needed only for flashing — unplugged at runtime. The Pi serial console must be disabled in `raspi-config` so `/dev/serial0` is free. LCD I2C pull-up cut required — see architecture spec §5.2.

## Build

```bash
pio run
```

First build downloads platform + libraries (~2–5 min).

## Flash

```bash
# Pi pyserial app must release /dev/ttyUSB0 first.
pio run -t upload
```

Reset is automatic via DTR/RTS on CP2102.

## Monitor

```bash
pio device monitor
```

Press Ctrl+T then Ctrl+H for the picocom-style help.

## UART protocol

See architecture spec §4. JSON Lines, 115200 baud (USB-CDC ignores baud but app config is symmetric with Pi).

Send a `ping`:

```
{"id":1,"type":"cmd","v":"ping"}
```

Expect:

```
{"type":"ack","id":1,"v":"ping","data":{"ok":true}}
```

## Acceptance tests (manual)

| # | Scenario | Expected serial output |
| --- | --- | --- |
| 1 | Power on board | One line `{"type":"evt","v":"boot","data":{"fw":"1.0.0","free_heap":N,"reset_reason":"power_on"}}` within 500 ms |
| 2 | Send `{"id":1,"type":"cmd","v":"ping"}` | `{"type":"ack","id":1,"v":"ping","data":{"ok":true}}` within 100 ms |
| 3 | Scan whitelisted card | `evt:rfid granted` with `name`; `evt:gate opening` → `evt:gate open` after 300 ms; LCD `"Welcome: <name>"`; servo physically opens |
| 4 | Pass hand through HC-SR04 beam | `evt:person_passed` with `distance_cm` and `ms`; `evt:gate closing` → `evt:gate closed` |
| 5 | Scan non-whitelisted card | `evt:rfid denied`; buzzer triple-beep; no gate motion |
| 6 | `cmd:open` then leave alone | `evt:gate opening` → `evt:gate open`; after 10 s `evt:gate timeout_warn` + buzzer warn pattern; after 5 s `evt:gate closing` → `evt:gate closed` |
| 7 | `add_uid` → `list_uids` → reboot → `list_uids` | Second `list_uids` after reboot still contains added UID |
| 8 | `remove_uid` for unknown UID | `ack` with `{"ok":false,"err":"not_found"}` |
| 9 | `cmd:config {"close_timeout_s":3}` then `cmd:open` and idle | Timeout warning fires at 3 s instead of 10 s |
| 10 | Disconnect Pi USB, scan whitelisted card | RFID auth still works end-to-end (boards standalone) |
| 11 | Send malformed JSON | `evt:log warn` with `tag:"uart"`; next valid message still processed |
| 12 | Hold whitelisted card on reader | `evt:rfid granted` fires once; identical events suppressed until card removed |

Record pass/fail in `firmware/test-log.md` (create on first acceptance run).

## Troubleshooting

- **`pio run -t upload` fails with "Resource busy"** — another process holds `/dev/ttyUSB0`. Stop the Pi app or `fuser -k /dev/ttyUSB0`.
- **No serial output at all** — check USB cable (some are charge-only), check `pio device list` for the right port name.
- **LCD shows garbage** — pull-up cut not done (architecture spec §5.2). Cut the on-backpack 4.7 kΩ pull-ups, the carrier PCB pull-ups to 3V3 take over.
- **RFID never reads** — confirm SPI wiring; the RC522 module's onboard regulator drops 3V3 if there's a short.
- **HC-SR04 always reads 0** — confirm voltage divider on ECHO (5 V → 3.3 V). Direct 5 V to GPIO 26 over time damages the input.
- **Servo jitters** — 470 µF cap on 5 V rail not installed (architecture spec §2.2).
