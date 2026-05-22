# Smart Gate — Architecture & Hardware Design Spec

**Date:** 2026-05-21 (last revised 2026-05-22)
**Status:** Design draft awaiting review
**Scope:** This spec covers system architecture, video streaming pipeline, Pi ↔ ESP32 communication protocol, ESP32 pin assignment, and mechanical envelope for a demo/prototype barrier gate. Firmware implementation, Pi-side application code, and KiCad/FreeCAD files are deliverables of subsequent plans, not this spec.

**2026-05-22 revision:** Architecture pivoted to a **single integrated motherboard** that hosts both the Raspberry Pi 4 (via a 2×20 GPIO socket the Pi plugs into) and the ESP32 DevKit (via a 30-pin socket). One 12 V power input feeds both subsystems through a 5 V/3 A buck regulator. See decisions #19–#22.

**2026-05-22 later revision — UART transport rollback:** Decision #21 (GPIO UART link between Pi and ESP32) is rolled back. Runtime application traffic and `esptool.py` firmware flashing both run over the **same USB cable** from a Pi USB-A port to the ESP32 DevKit USB-C/micro-USB port; exposed on Pi as `/dev/ttyUSB0`. Rationale: matches the existing firmware pin map (`firmware/include/config.h` keeps GPIO 5/17 as RC522 CS/RST), removes the `raspi-config` console-disable step, eliminates a separate physical wire pair, and gives the Pi-side instant link-down detection on USB disconnect. The §4.1 transport bullets reflect this rollback. The §5 ESP32 pin table and §5.2 Pi GPIO mapping still describe the now-superseded GPIO UART variant; they remain to be re-reconciled with the firmware in a follow-up design-session sweep. See decision #23.

---

## 1. Overview

`smart_gate` is a demo/prototype access-control barrier built around a **single integrated motherboard** (`smart_gate_combined`) that hosts two compute nodes side-by-side:

- **Raspberry Pi 4** plugs into a 2×20 female GPIO socket on the motherboard. It runs the vision pipeline (face recognition + QR scan from a USB webcam), Flask web admin (live MJPEG preview + event log), event recorder, and user database. It is the "host" of the system.
- **ESP32-WROOM-32** (DOIT V1 30-pin DevKit) sockets into a 2×15 pin socket on the same motherboard. It is the real-time controller for the RFID reader (RC522), servo (SG90 barrier arm), LCD 20×4 status display, HC-SR04 ultrasonic passage sensor, and an active buzzer.

Pi and ESP32 share a single **12 V DC power input** stepped down to 5 V/5 A by an on-board buck regulator. The 5 V rail powers the Pi via the GPIO header pins 2/4, and powers all peripheral modules. A 3.3 V LDO (AMS1117-3.3) on the 5 V rail powers the ESP32 logic; the Pi has its own onboard 3.3 V regulator.

Pi↔ESP32 application communication uses **USB-CDC** over a single USB cable from a Pi USB-A port to the ESP32 DevKit's USB-C (or micro-USB) port. The same cable carries `esptool.py write_flash @ 921600` during firmware updates; the Pi daemon releases `/dev/ttyUSB0` (via `sudo systemctl stop smart-gate`) before flashing and reacquires it after. `pyserial` opens the port with `dsrdtr=False, rtscts=False` and forces DTR/RTS low so the open does not toggle the CP2102/CH340 EN line and reset the ESP32 (see `smart_gate/link/uart_client.py::_open_serial`). **No Wi-Fi on ESP32; no MQTT.** ESP32 maintains its own NVS-stored RFID allowlist so it can authenticate RFID and operate the barrier independently if the Pi link is lost.

The mechanical demo is a tabletop barrier-arm style gate (~300 × 200 × 100 mm overall envelope) cut from 3 mm MDF/acrylic, with 3D-printed brackets for the servo. The motherboard PCB is ~250 × 150 mm to accommodate the Pi + ESP32 + peripherals on one substrate.

---

## 2. System Architecture

### 2.1 Block diagram

```
                       ┌────────────────────────────────────────┐
                       │  Single motherboard ~250 × 150 mm      │
                       │                                        │
        ┌────────────┐ │  ┌──────────────────────────────────┐  │
        │ 12V DC jack├─┤─▶│ Reverse-protect (1N5817) + bulk  │  │
        │  3 A adapt │ │  │ 100 µF → Buck 5V/5A module       │  │
        └────────────┘ │  └────────────┬─────────────────────┘  │
                       │               │ +5V rail                │
                       │               │                         │
                       │   ┌───────────┴─────┐    ┌──────────┐  │
                       │   │ Pi 5V (pin 2/4) │    │AMS1117LDO│  │
                       │   │ +1000µF +ferrite│    │ +caps    │  │
                       │   │ +TVS protection │    └────┬─────┘  │
                       │   └────────┬────────┘         │ +3V3   │
                       │            │                   │        │
                       │      ┌─────┴───────┐          │        │
                       │      │ 2×20 socket │          │        │
                       │      │  Pi 4 plugs │          │        │
                       │      │ into here   │          │        │
                       │      └──┬─────┬────┘          │        │
                       │         │  pin8/10 (UART)     │        │
                       │         │     │               │        │
                       │         │     ▼               │        │
                       │         │  ┌────────────────┐ │        │
                       │         │  │ ESP32 DevKit   │◀┘        │
                       │         │  │ (2× 15p socket)│          │
                       │         │  │ UART1 GPIO 5/17│          │
                       │         │  └──┬──────┬──────┘          │
                       │         │     │      │                 │
                       │         │  Periphs   │                 │
                       │         │  RC522 SPI │                 │
                       │         │  LCD I2C   │                 │
                       │         │  HC-SR04   │                 │
                       │         │  Servo PWM │                 │
                       │         │  Buzzer    │                 │
                       │         │  J_EXP     │                 │
                       │         └────────────┘                 │
                       └────────────────────────────────────────┘

        Pi 4 (plugged in)             ESP32 firmware flash path:
        --------------                ----------------------
        - USB webcam                  - Pi USB-A ─── micro-USB DevKit
        - HDMI / Wi-Fi LAN            - esptool.py @ 921600
        - power IN via GPIO 5V
        - UART app comm via GPIO 14/15
```

### 2.2 Power

- **Input**: 12 V DC barrel jack, 3 A rated. Reverse-protection diode (1N5817), 100 µF bulk cap.
- **5 V rail**: 12 V → 5 V/3 A buck converter module (MP1584, LM2596, MP2307, or equivalent — 3 A continuous is enough for Pi 4 + peripherals). Filter: 1000 µF + ferrite bead + 100 nF on the Pi GPIO 5V feed, plus a TVS diode (SMAJ5.0A) for transient protection.
- **3.3 V rail (ESP32 side only)**: sourced from the ESP32 DevKit's onboard AMS1117-3.3 regulator via the DevKit 3V3 pin (J_ESP pin 1) — no separate LDO on the motherboard. External 3V3 load is ~31 mA (RC522 ~30 mA + LCD I2C pull-ups ~1.4 mA), well within the DevKit LDO's ~500 mA budget. Pi has its own onboard 3.3 V regulator; the Pi 3V3 pin is left unconnected on the motherboard.
- **Pi power feed**: 5 V rail → Pi GPIO header pin 2 (5V) and pin 4 (5V). This bypasses the Pi's USB-C PD power management and the back-powering protection diode. The buck regulator's output stability is therefore safety-critical.
- **Common ground**: 5 V GND → multiple Pi GND pins (6, 9, 14, 20, 25, 30, 34, 39) for low-impedance return.

Estimated current draw (peak):
- 3V3 rail: ESP32 (120 mA) + RC522 (30 mA) ≈ **150 mA**
- 5V rail: Pi 4 (1500 mA peak with camera + ML) + LCD (50 mA) + HC-SR04 (15 mA) + SG90 inrush (500 mA) + buzzer (30 mA) ≈ **2.1 A peak**
- 12V input @ ~85% buck efficiency: 5 V × 2.1 A / 0.85 / 12 V ≈ **1.0 A peak** — well within 3 A adapter rating.

Bulk caps required on the 5 V rail:
- 1000 µF / 10 V near the Pi GPIO power pins (Pi PMIC needs steady supply)
- 470 µF / 16 V near the SG90 servo connector (absorbs servo inrush)
- 100 µF + 10 µF on the buck output before any branches

A ferrite bead between the buck output and Pi feed isolates servo switching noise from Pi.

---

## 3. Video Streaming Pipeline (Pi side)

### 3.1 Camera

**USB UVC webcam** (e.g., Logitech C270 entry-level, or C920 if 1080p is wanted). Plugged into a Pi 4 USB 3.0 port. Pi Camera Module 3 (CSI ribbon) was considered and rejected because USB is easier to mount on the demo stand and the user already has a USB webcam.

### 3.2 Capture loop

A single thread runs:

```python
cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))   # native MJPEG passthrough
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 15)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)   # drop old frames, always return latest
```

The MJPG FOURCC is required: it instructs the webcam to deliver pre-encoded JPEG (the webcam does the encode), avoiding USB bandwidth blowout from raw YUYV and saving Pi CPU. `BUFFERSIZE=1` prevents stale frames accumulating in the V4L2 buffer when the detector is slow.

For each captured frame:
1. `cap.read()` returns a decoded BGR ndarray.
2. The capture thread re-encodes a 75-quality JPEG with `cv2.imencode('.jpg', ...)`.
3. Both (JPEG bytes, BGR ndarray) are published to `FrameHub`.

This software fan-out is necessary because USB UVC, unlike CSI/libcamera, produces a single stream per sensor.

### 3.3 FrameHub

A `threading.Condition` + latest-frame storage:

```python
class FrameHub:
    def publish(self, jpeg_bytes, bgr): ...   # holds latest of each, notify_all()
    def wait_jpeg(self): ...                  # blocks until next frame, returns latest jpeg
    def wait_bgr(self): ...                   # blocks until next frame, returns latest bgr
```

Three consumer threads block on the hub. Each is woken by `notify_all` on every new frame and reads the latest values — no per-consumer queue.

### 3.4 Consumers

**(a) Flask `/stream.mjpeg`** — multipart/x-mixed-replace endpoint. Generator yields `--FRAME` boundary + JPEG bytes for each new frame. Browser renders via `<img src="/stream.mjpeg">` natively. No JavaScript needed. Glass-to-glass latency: 50–300 ms over LAN.

**(b) Detector thread** — reads decoded BGR. Runs MediaPipe Face Detection / `face_recognition` for face matching against stored face encodings, and `pyzbar` for QR. On a match, writes a `cmd:open` over the serial link to ESP32 (see §4). The exact SQLite schema (users table, face encoding column type, QR code mapping) is out of scope for this spec — defined in the subsequent Pi-application plan.

**(c) Ring recorder** — keeps the last ~5 seconds of JPEGs in a deque. When an event fires, the recorder writes JPEGs covering 5 s before + 5 s after the event into a temporary directory, then invokes `ffmpeg -framerate 15 -i %05d.jpg -c:v libx264 -y event.mp4` to produce a single mp4 clip. Clip path is recorded in the `events` table.

### 3.5 Why MJPEG (not HLS or WebRTC)

- **HLS**: 2–6 s latency is unacceptable for live monitoring of a security gate.
- **WebRTC**: <100 ms latency, but requires aiortc + STUN/signaling. Overkill for one admin viewer on a LAN; ~300 lines of additional code.
- **MJPEG over HTTP**: ~50 lines of Python, browser-native rendering, 200–500 ms latency on LAN — the right tool for this scope.

---

## 4. Pi ↔ ESP32 Protocol (USB-CDC, JSON Lines)

### 4.1 Transport

- Physical: a single USB cable, Pi USB-A → DevKit USB-C (or micro-USB depending on DevKit variant).
- Pi side: `/dev/ttyUSB0` (CP2102 or CH340 on the DevKit) at 115200 baud, 8N1, no flow control. USB-CDC ignores baud at the USB layer; 115200 is the configured app rate for symmetry.
- ESP32 side: UART0 (GPIO 1 TX, GPIO 3 RX), wired internally on the DevKit to the CP2102/CH340 USB-UART chip. No GPIO repurposing on the ESP32 for runtime comm; GPIO 5/17 stay free for RC522 CS/RST per the firmware pin map.
- `pyserial` open: `Serial(port, baud, timeout=1.0, dsrdtr=False, rtscts=False)` plus `ser.dtr = False; ser.rts = False`. On CP2102/CH340 boards, DTR is wired to the EN line — leaving the default open behaviour would reset the ESP32 every time the daemon reconnects. See `smart_gate/link/uart_client.py::_open_serial`.
- The same physical cable is used for `esptool.py write_flash @ 921600` during firmware updates. The Pi daemon must release the port first (`sudo systemctl stop smart-gate`).
- **Power note:** the USB cable also carries 5 V VBUS from the Pi USB host to the DevKit. If the ESP32 has its own external 5 V supply (recommended to handle SG90 servo inrush spikes that could brown out the Pi USB host), keep VBUS isolated — either cut the VBUS conductor on the cable or open the DevKit's USB-VBUS jumper. The motherboard variant routes ESP32 power from its own 5 V buck and the USB cable should carry data only.

### 4.2 Frame format

One message = one line of UTF-8 JSON terminated by `\n`. Maximum line length: **512 bytes** (defensive cap; typical message <200 bytes).

```json
{"id": 42, "type": "cmd", "v": "open", "data": {"user": "alice", "reason": "face"}}
```

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | when ack expected | Pi-assigned monotonically increasing integer per session. ESP32 echoes it in the corresponding `ack`. Omitted for events. |
| `type` | yes | `"cmd"` (Pi→ESP32), `"evt"` (ESP32→Pi event), `"ack"` (ESP32→Pi reply to a cmd) |
| `v` | yes | Verb. See §4.3, §4.4. |
| `data` | per verb | Object payload; may be omitted for nullary verbs. |

No CRC: USB-CDC provides USB-level CRC. No length prefix: newline framing is enough. JSON parser errors → receiver drops the line and continues.

### 4.3 Command verbs (Pi → ESP32)

| Verb | Data | Ack data | Purpose |
| --- | --- | --- | --- |
| `open` | `{"user":"alice","reason":"face"}` | `{"ok":true}` | Pi has authenticated via face/QR; ESP32 opens the barrier. |
| `close` | — | `{"ok":true}` | Force immediate close (admin override). |
| `add_uid` | `{"uid":"a1b2c3d4","name":"alice"}` | `{"ok":true,"total":N}` | Add UID to NVS allowlist. |
| `remove_uid` | `{"uid":"a1b2c3d4"}` | `{"ok":true}` or `{"ok":false,"err":"not_found"}` | Remove UID. |
| `list_uids` | — | `{"uids":[{"uid":"...","name":"..."}, ...]}` | Dump the allowlist. |
| `config` | `{"close_timeout_s":10,"servo_open_deg":100,"servo_close_deg":10}` | `{"ok":true}` | Update runtime parameters; persisted in NVS. |
| `status` | — | `{"uptime_s":N,"free_heap":N,"gate":"idle","fw":"1.0.0"}` | Snapshot. |
| `ping` | — | `{"ok":true}` | Liveness probe (Pi sends every 5 s; 2 s timeout = link dead). |

### 4.4 Event verbs (ESP32 → Pi)

| Verb | Data | When |
| --- | --- | --- |
| `boot` | `{"fw":"1.0.0","free_heap":N,"reset_reason":"power_on"}` | Once after FreeRTOS tasks ready. |
| `rfid` | `{"uid":"...","result":"granted","name":"alice"}` or `{"uid":"...","result":"denied"}` | Each card scan. |
| `gate` | `{"state":"opening"\|"open"\|"closing"\|"closed"\|"timeout_warn"}` | State transitions. |
| `person_passed` | `{"distance_cm":N,"ms":N}` | HC-SR04 detects passage (distance reading transitions from "in range" to "out of range"). |
| `heartbeat` | `{"uptime_s":N,"free_heap":N,"gate":"idle"}` | Every 10 s. Pi watchdog: 30 s without heartbeat → link dead. |
| `log` | `{"lvl":"info"\|"warn"\|"err","tag":"servo","msg":"..."}` | Debug messages from ESP32; Pi writes to file log. |

### 4.5 Gate state machine (ESP32 side)

```
IDLE
  ─( cmd:open ∨ RFID granted )──▶ OPENING     [emit gate:opening; LEDC writes OPEN PWM duty]
OPENING
  ─( 300 ms timer elapsed )─────▶ OPEN_WAIT   [emit gate:open; start 10 s passage timer]
OPEN_WAIT
  ─( HC-SR04 detects passage )──▶ CLOSING     [emit person_passed; emit gate:closing; LEDC writes CLOSE duty]
  ─( 10 s elapsed )─────────────▶ TIMEOUT_WARN [emit gate:timeout_warn; buzzer pattern]
TIMEOUT_WARN
  ─( passage detected )─────────▶ CLOSING     [emit person_passed; emit gate:closing]
  ─( 5 s elapsed )──────────────▶ CLOSING     [emit gate:closing]
CLOSING
  ─( 300 ms timer elapsed )─────▶ IDLE        [emit gate:closed]
```

SG90 has no position feedback; "servo target reached" is implemented as a 300 ms timer after the PWM duty is updated (SG90 ≈ 300°/s, 90° sweep ≈ 300 ms — round up if needed via `config`).

Repeated `cmd:open` while in OPEN_WAIT resets the 10 s passage timer (admin can hold the gate open).

### 4.6 Failure modes

- **Pi unplugs cable / Pi crashes**: ESP32 keeps operating. RFID auth runs against local NVS; gate cycle works normally. Heartbeat from Pi missing → ESP32 only notes it in its own log (does not raise an alert, since ESP32 may legitimately run standalone).
- **ESP32 reboots**: Pi receives a fresh `evt:boot`. Pi may resend configuration as a safety re-sync.
- **Malformed JSON**: receiver drops the line. ESP32 emits an `evt:log warn` on parse error.
- **USB-CDC backpressure**: at <10 messages/s and ~200 B/msg, the kernel buffer (~64 KB) is never close to full. Not a concern.

---

## 5. Pin Assignment

### 5.1 ESP32-WROOM-32 (DOIT V1 30-pin DevKit, socketed)

Because the 30-pin variant does **not** expose IO18/19/21/22/23 on its headers, the default VSPI and I2C pin assignments cannot be used. Peripherals are remapped via the ESP32 GPIO matrix.

| GPIO | Direction | Peripheral | Notes |
| --- | --- | --- | --- |
| 1 | OUT (UART0 TX) | USB-CDC TX | Reserved. Firmware flash + debug log only. |
| 3 | IN (UART0 RX) | USB-CDC RX | Reserved. |
| 2 | OUT (strap) | Onboard status LED | Strap: must not be pulled HIGH at boot. Driver writes HIGH/LOW after boot. |
| 14 | OUT | RC522 SCK | Remapped VSPI. |
| 13 | OUT | RC522 MOSI | Remapped VSPI. |
| 35 | IN only | RC522 MISO | Input-only pin; MISO is always input from RC522 → ESP32. RC522 drives push-pull, no pull-up needed. |
| 15 | OUT (strap) | RC522 CS | Strap: HIGH at boot. RC522 CS idle HIGH ⇒ compatible. |
| 4 | OUT | RC522 RST | Active LOW; pull HIGH during operation. |
| 16 | IN | RC522 IRQ | Optional; FALLING edge interrupt. |
| 32 | I/O | LCD I2C SDA | Remapped I2C. 4.7 kΩ pull-up to **3.3 V**. |
| 33 | OUT | LCD I2C SCL | Remapped I2C. 4.7 kΩ pull-up to **3.3 V**. |
| 25 | OUT | HC-SR04 TRIG | 10 µs pulse. 3.3 V output usually triggers HC-SR04 OK; add BS170 level shifter if marginal. |
| 34 | IN only | HC-SR04 ECHO | **Voltage divider mandatory**: R1=1 kΩ in series, R2=2 kΩ to GND → 5 V echo becomes ~3.3 V at GPIO 34. |
| 26 | OUT | Servo SG90 PWM | LEDC channel 0, 50 Hz, 1–2 ms pulse. 3.3 V exceeds SG90 input threshold. |
| 27 | OUT (digital) | Active buzzer | Plain GPIO HIGH/LOW; buzzer has internal oscillator. Drive via NPN 2N3904 + 1 kΩ base resistor. |
| **17** | **OUT (UART1 TX)** | **→ Pi pin 10 (RX0)** | **Runtime app comm to Pi**. UART1 remapped via GPIO matrix. |
| **5** | **IN (UART1 RX, strap)** | **← Pi pin 8 (TX0)** | **Runtime app comm from Pi**. Strap HIGH at boot ⇒ compatible with idle-HIGH UART RX line. |
| 6–11 | — | **DO NOT USE** | Connected to internal SPI flash. Not exposed on the 30-pin header. |
| 12 | — | **DO NOT USE** | Strap pin: must be LOW at boot for 3.3 V flash voltage. Leaving floating is safest. |
| 36, 39 | IN only | Unused / spare | ADC1 capable; bring out to expansion header. |

Free GPIOs reserved for the expansion header: 36, 39 (plus +3V3 and GND). GPIO 12 excluded (strap), GPIO 17/5 now consumed by Pi UART.

### 5.2 Raspberry Pi 4 GPIO header (2×20, plugged into motherboard)

| Pi pin | BCM GPIO | Function | Motherboard connection |
| --- | --- | --- | --- |
| 1 | — | 3V3 (Pi out) | Not connected (Pi has its own LDO; ESP32 has its own LDO; isolate rails) |
| **2** | — | **5V (Pi in)** | **Motherboard 5V buck output → Pi POWER IN** |
| **4** | — | **5V (Pi in)** | **Motherboard 5V buck output → Pi POWER IN** (parallel pin 2) |
| 6, 9, 14, 20, 25, 30, 34, 39 | — | GND | Common ground (multiple for low-impedance return) |
| **8** | GPIO14 (TX0) | UART0 TX | **→ ESP32 GPIO 5 (UART1 RX)** |
| **10** | GPIO15 (RX0) | UART0 RX | **← ESP32 GPIO 17 (UART1 TX)** |
| Others (3, 5, 7, 11, 12, 13, ..., 40) | various | Spare | Left unconnected on the motherboard but routed to a Pi-side breakout header for future expansion |

Pi UART0 console must be **disabled in `raspi-config`** (`Interface Options → Serial Port → No to login shell, Yes to serial hardware`) before the UART link works. Otherwise the kernel grabs `/dev/serial0` for login output and ESP32 messages collide with the boot log.

### 5.3 LCD I2C level handling

The PCF8574 backpack on most cheap LCD 20×4 modules runs at 5 V VCC and has 4.7 kΩ pull-ups to its 5 V rail. Driving its SDA/SCL with ESP32 3.3 V output is electrically OK in the LOW state, but the 5 V pull-up will back-drive the ESP32 protection diodes when the bus floats HIGH. The recommended fix is one of:

1. **Cut the on-backpack pull-up traces**, add 4.7 kΩ pull-ups on the motherboard tied to 3.3 V.
2. **Add a bidirectional level shifter** (BSS138 board, ~5 k VND) between ESP32 and LCD.

Option 1 is cheaper and is the spec'd approach. Document the cut in the assembly notes.

### 5.4 Strap pin discipline (ESP32)

- GPIO 0 (BOOT button): unused by app; the BOOT button is for entering download mode at reset.
- GPIO 2 (LED): driver writes HIGH/LOW for status; do not add external pull-up.
- GPIO 5 (strap HIGH at boot): used as UART1 RX. UART idle line is HIGH ⇒ compatible.
- GPIO 12 (strap LOW at boot): **left floating; do not route to expansion header**.
- GPIO 15 (strap HIGH at boot): used as RC522 CS. CS idle HIGH ⇒ compatible.

### 5.1 Strap pin discipline

- GPIO 0 (BOOT button): unused by app; the BOOT button is for entering download mode at reset.
- GPIO 2 (LED): driver writes HIGH/LOW for status; do not add external pull-up. Must not be pulled HIGH at boot — onboard circuitry handles this.
- GPIO 5 (strap HIGH at boot): unused; if brought to expansion header, downstream user must not pull LOW at power-on.
- GPIO 12 (strap LOW at boot): **left floating; do not route to expansion header**.
- GPIO 15 (strap HIGH at boot): used as RC522 CS. CS idle HIGH ⇒ compatible with strap requirement.

### 5.2 LCD I2C level handling

The PCF8574 backpack on most cheap LCD 20×4 modules runs at 5 V VCC and has 4.7 kΩ pull-ups to its 5 V rail. Driving its SDA/SCL with ESP32 3.3 V output is electrically OK in the LOW state, but the 5 V pull-up will back-drive the ESP32 protection diodes when the bus floats HIGH. The recommended fix is one of:

1. **Cut the on-backpack pull-up traces**, add 4.7 kΩ pull-ups on the carrier PCB tied to 3.3 V.
2. **Add a bidirectional level shifter** (BSS138 board, ~5 k VND) between ESP32 and LCD.

Option 1 is cheaper and is the spec'd approach. Document the cut in the assembly notes.

---

## 6. Mechanical Envelope (FreeCAD)

### 6.1 Overall geometry

Barrier-style demo gate. Two posts flank a 60 mm lane; an 80 mm arm rotates 90° between horizontal (CLOSED) and vertical (OPEN). Overall footprint **~300 × 200 mm** (revised 2026-05-22 to accommodate the combined motherboard ~250×150 mm), height ~100 mm. Camera stand separate, ~250 mm tall.

### 6.2 Parts list

| Part | Dimensions (mm) | Material | Notes |
| --- | --- | --- | --- |
| Base box | 300 × 200 × 50 | MDF 3 mm, laser-cut, finger joints | Houses the combined motherboard (~250×150 mm) with Pi 4 plugged in on top via the 2×20 GPIO socket. Height increased for Pi-on-socket stack clearance (~25 mm above PCB). |
| Left post (servo) | 30 × 30 × 60 | MDF 3 mm (6-panel hollow) | SG90 mounted horizontally; horn exits right face. |
| Right post (rest) | 30 × 30 × 60 | MDF 3 mm (6-panel) | Top has a notched rest pad with foam liner. |
| Arm | 80 × 8 × 3 | Balsa or acrylic | Painted red/yellow stripes; M2 screw to servo horn + glue. |
| Servo bracket | ~25 × 25 × 25 | 3D printed PLA | Two M3 holes for SG90 ears; bolts down to inside of left post. |
| Webcam stand | dia 8 × 250 + base 80 × 80 | Wooden dowel + MDF base | Webcam clips on top, faces lane at ~30° downward. USB cable to Pi USB-A port. |
| Front panel of base | 300 × 50 | MDF 3 mm with cutouts | LCD 98 × 24, RC522 60 × 40, HC-SR04 2 × Ø16, LED Ø3, buzzer Ø8. |
| Back panel of base | 300 × 50 | MDF 3 mm with cutouts | 12 V DC barrel jack Ø8 (motherboard input), Pi 4 access cutouts (HDMI 18×7, USB ports 14×10 × 4, Ethernet 16×14), 6 ventilation slots. Note: Pi USB-C is unused since power comes via GPIO 5V. |

### 6.3 Servo motion parameters

SG90 with 50 Hz PWM:

- `servo_close_deg = 10°` — arm horizontal, resting in right-post notch
- `servo_open_deg = 100°` — arm vertical, lane clear
- Sweep time ≈ 300 ms (SG90 nominal 300°/s).

These are firmware-tunable via `cmd:config`.

### 6.4 FreeCAD deliverables

| File | Type | Purpose |
| --- | --- | --- |
| `smart_gate_assembly.FCStd` | Parametric assembly | Top-level. Spreadsheet-driven: `base_w`, `base_d`, `base_h`, `post_w`, `arm_len`, `lane_w`. Sub-assemblies linked. |
| `panels.FCStd` | 2D sketches | One sketch per laser-cut panel. Export DXF for laser shop. |
| `servo_bracket.FCStd` | 3D solid | Export STL for 3D print. |
| `arm_coupling.FCStd` | 3D solid (optional) | If gluing arm to horn is not preferred. |
| `step_export/*.step` | Auto export | For KiCad 3D viewer to verify carrier PCB fits inside base box. |

---

## 7. Decision Log

Decisions made during 2026-05-21 design session, in order:

1. **Gate type**: Demo/prototype tabletop model (small, MDF/acrylic). Not full-size pedestrian or car gate.
2. **MCU**: ESP32-WROOM-32 classic. (S3/C3 not needed; WROOM-32 has enough GPIO.)
3. **Power input**: 12 V DC barrel jack + buck → 5 V → LDO → 3.3 V. (Not USB-only, not battery.)
4. **RFID**: RC522 SPI module (cheap, well-supported).
5. **Display**: LCD 20×4 with I2C PCF8574 backpack. (Larger than 16×2 — more status info room.)
6. **Audio**: Active buzzer (user already has one — has internal oscillator, driven by digital HIGH/LOW). NPN 2N3904 transistor required because buzzer draws more than ESP32's safe per-pin current.
7. **Passage sensor**: HC-SR04 ultrasonic. *Revision from requirement.txt which originally said "IR sensor".* Ultrasonic is more robust in varied lighting.
8. **Camera**: USB UVC webcam (user already has). Pi Camera Module 3 was considered but USB is easier for the chosen mount.
9. **Camera streaming**: MJPEG over HTTP multipart via Flask, served on LAN to admin browser. HLS too laggy; WebRTC overkill.
10. **Pi ↔ ESP32 link**: single USB cable, no Wi-Fi, no MQTT. Same cable used for both `pyserial` app comm and `esptool.py` firmware flashing.
11. **RFID auth location**: ESP32 local NVS. Pi only sends `cmd:open` after face/QR auth; RFID is fully independent of Pi. Resilient if Pi crashes.
12. **PCB topology**: ESP32 DevKit socketed into a carrier PCB. (Not bare WROOM-32 + on-board USB-UART — too complex for prototype.)
13. **Wi-Fi & MQTT**: Removed. UART/USB-CDC handles all Pi↔ESP32 traffic.
14. **Web admin viewer**: Pi Flask admin shows live MJPEG + event list. Event recorder writes 10 s clips (5 s pre + 5 s post) on each authentication event using ffmpeg.
15. **Gate mechanism**: Barrier arm rotated by SG90 servo. *Revision from requirement.txt which said "sliding door".* Mechanically simpler than rack/pulley/rail.
16. **Barrier layout**: Two posts (one with servo, one rest pad) + base box for electronics. Arm 80 mm, lane 60 mm.
17. **Material**: 3 mm MDF/acrylic laser-cut for box and posts; 3D-printed PLA bracket for servo mount.
18. **DevKit variant** (2026-05-22): user confirmed **DOIT V1 30-pin**. Since IO18/19/21/22/23 are not exposed on the 30-pin header, the pin assignment in §5 was revised: SPI and I2C use remapped GPIOs via the ESP32 GPIO matrix (SCK=14, MOSI=13, MISO=35, SDA=32, SCL=33). VSPI/I2C default pins are no longer referenced.
19. **Single combined motherboard** (2026-05-22): pivoted from two separate boards (Pi 4 standalone + ESP32 carrier connected by USB cable) to one ~250×150 mm motherboard that hosts both. Pi 4 plugs into a 2×20 female GPIO socket on the motherboard; ESP32 DevKit sockets in alongside. Existing ESP32-only KiCad project (`smart_gate_carrier_v1_esp32only`) preserved under `kicad/archive/` for reference. **Why:** user requested a single integrated PCB to reduce part count and inter-board cabling at the cost of a larger PCB.
20. **Single 12 V PSU for both Pi and ESP32** (2026-05-22): the 12 V DC input is stepped down by an on-board 5 V/5 A buck regulator (XL4015 or MP4560-class module). The 5 V rail feeds the Pi via GPIO pin 2/4, the peripherals (LCD 5V, servo, HC-SR04, buzzer), and the AMS1117-3.3 LDO that derives 3.3 V for the ESP32. **Trade-off accepted:** powering Pi through GPIO bypasses its USB-C PD power-management chip, so 5 V rail stability (≥1000 µF bulk, ferrite bead, TVS) is now safety-critical for Pi.
21. **UART app comm via Pi GPIO 14/15** (2026-05-22): runtime Pi↔ESP32 traffic moves from USB-CDC (`/dev/ttyUSB0`) to a hardware UART link on the Pi GPIO header pins 8/10 → ESP32 GPIO 5/17 (UART1 via the ESP32 GPIO matrix). Pi serial console must be disabled in `raspi-config` for `/dev/serial0` to be available. **(SUPERSEDED 2026-05-22 later — see decision #25.)**
22. **USB cable retained for ESP32 firmware flashing only** (2026-05-22): the GPIO UART has no DTR/RTS to auto-reset the ESP32 bootloader, so a Pi-to-DevKit micro-USB cable is kept solely for `esptool.py write_flash`. Once flashed, the cable can be unplugged; app comm runs over the GPIO UART instead. **(SUPERSEDED 2026-05-22 later — see decision #25.)**
23. **All-through-hole (THT) component preference** (2026-05-22): user explicitly chose THT over SMD for all discrete components on the motherboard to enable hand-soldering without a hot-air or reflow station. Footprint conventions: resistors `R_Axial_DIN0207_*` (1/4 W axial), small caps `C_Disc_D5.0mm_*` (ceramic disc), polarized caps `CP_Radial_*` (already THT), LDO `LM1117-3.3` in TO-220-3 (not AMS1117 in SOT-223), TVS `D_DO-15_*`, transistor 2N3904 TO-92 (already THT), inductor axial THT. Pre-made off-the-shelf modules (buck converter) remain represented as headers — user solders the module's pin row into the motherboard.
24. **Target Pi is Raspberry Pi 4** (2026-05-22, clarified): user uses Pi 4, not Pi 5. GPIO layout identical (40-pin 2×20), but power requirements relaxed: Pi 4 typical ~600 mA idle, ~1.5 A peak under camera+ML load — a 5 V/3 A buck module is enough (Pi 5 would need 5 A). Pi 4 also lacks the strict 5 V PMIC of Pi 5, so GPIO-fed 5 V is more forgiving in practice.
25. **UART rollback to USB-CDC** (2026-05-22 later, post-implementation): supersedes decisions #21 and #22. Runtime and `esptool.py` flash both share **one USB cable** from a Pi USB-A port to the DevKit USB-C/micro-USB port, exposed on Pi as `/dev/ttyUSB0`. Drivers: existing firmware (`firmware/include/config.h`) keeps GPIO 5/17 as RC522 CS/RST so the GPIO UART pin reassignment never landed; existing Pi-app code already targets `/dev/ttyUSB0`; eliminating the GPIO UART removes the `raspi-config` step, the level-matching consideration, and one physical wire pair. User confirmed they will supply ESP32 stack power externally (separate 5 V/2 A adapter recommended for servo inrush headroom), so VBUS on the USB cable should be cut or jumpered out to avoid Pi-USB-host current contention. Pi-app `_open_serial` sets `dsrdtr=False, rtscts=False` and forces DTR/RTS low after open so the daemon does not auto-reset the ESP32 every reconnect. §5 ESP32 pin table and §5.2 Pi GPIO mapping still describe the GPIO UART variant and need a follow-up reconciliation sweep in the design session (separate task).

---

## 8. Out of scope (deferred to future plans)

- Firmware implementation for ESP32 (FreeRTOS task design, ArduinoJson integration, NVS schema). → next plan.
- Pi 4 application code (Flask routes, SQLite schema, face encoding storage, ffmpeg invocation). → next plan.
- KiCad schematic + PCB layout of the ESP32 carrier. → next plan.
- FreeCAD parametric model files. → next plan.
- Webcam model selection (C270 vs C920 vs other) — performance characterisation not part of this design doc.
- OTA update mechanism — explicitly out of scope. Re-flash via `esptool.py` over USB is the supported update path.
- Multi-gate or cloud deployment — explicitly out of scope. If this changes, MQTT/Wi-Fi may need to be reintroduced.

---

## 9. Risks / open items

1. **LCD I2C pull-up cut** is an assembly step that varies by LCD module vendor. The first build may need debug if a particular backpack PCB makes the cut hard.
2. **HC-SR04 3.3 V trigger** usually works but not guaranteed across all clones. If pulses are unreliable, add a BS170 N-MOSFET level shifter on the TRIG line.
3. **Webcam autofocus & exposure variance** between different USB cams will affect face recognition accuracy. The vision pipeline should be tunable (target frame size, exposure mode) — not part of this design doc but should be a knob in the Pi plan.
4. **Servo current spikes** on the same 5 V rail as RC522 / LCD may cause RC522 read errors during open/close. The 470 µF cap on the 5 V rail (§2.2) is the first line of defence; if RC522 reads still glitch during arm motion, add a ferrite bead in series between the servo connector and the rest of the rail during PCB revision.
5. **Mechanical play in the arm-to-horn joint**: glue vs screw. First prototype: glue. If arm wobbles, add a 3D-printed coupler.
6. **Pi 4 powered through GPIO 5V is a known-risk path** — bypasses the Pi's USB-C PD power management. The 5 V buck must deliver clean 5 V ±5% under transient load (Pi 4 can spike from 0.8 A idle to 5 A peak in milliseconds). If the rail dips below 4.75 V the Pi PMIC will brown-out. Mitigations specified: 1000 µF bulk cap at Pi GPIO, ferrite bead between buck output and Pi feed, TVS SMAJ5.0A for transient clamp. If reliability problems appear during prototyping, fall back to the dual-PSU architecture (Pi USB-C + separate 12 V motherboard input) — the motherboard layout has provision for jumpering the Pi 4V input pin to either source.
7. **Pi serial console must be disabled** in `raspi-config` before the GPIO UART link works. Easy to forget; first boot of a fresh Pi image typically has the console enabled, so the ESP32 will see garbage data interleaved with kernel boot output. Document this in the Pi setup guide.
8. **Buck regulator current rating** — many "5A" buck modules on Vietnamese marketplaces are mislabeled and actually only deliver 3 A continuous. Source the module from a reputable seller or use a name-brand IC (TI TPS54561, MPS MP4560) on the motherboard. Verify with a load test before powering the Pi.

---

*End of design doc.*
