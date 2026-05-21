# Smart Gate — Architecture & Hardware Design Spec

**Date:** 2026-05-21
**Status:** Design draft awaiting review
**Scope:** This spec covers system architecture, video streaming pipeline, Pi ↔ ESP32 communication protocol, ESP32 pin assignment, and mechanical envelope for a demo/prototype barrier gate. Firmware implementation, Pi-side application code, and KiCad/FreeCAD files are deliverables of subsequent plans, not this spec.

---

## 1. Overview

`smart_gate` is a demo/prototype access-control barrier with two compute nodes:

- **Raspberry Pi 5** — runs vision pipeline (face recognition + QR scan from a USB webcam), Flask web admin (live MJPEG preview + event log), event recorder, and user database. It is the "host" of the system.
- **ESP32-WROOM-32** (on a custom carrier PCB with socketed DevKit) — real-time controller for RFID reader (RC522), servo (SG90 barrier arm), LCD 20×4 status display, HC-SR04 ultrasonic passage sensor, and a buzzer.

Pi and ESP32 communicate over **a single USB cable** (Pi USB-A → DevKit micro-USB). The same cable is used for ESP32 firmware flashing (`esptool.py` from Pi) and runtime application messaging (`pyserial` + JSON Lines). **No Wi-Fi on ESP32; no MQTT.** ESP32 maintains its own NVS-stored RFID allowlist so it can authenticate RFID and operate the barrier independently if the Pi link is lost.

The mechanical demo is a tabletop barrier-arm style gate (~200 × 100 × 100 mm overall envelope) cut from 3 mm MDF/acrylic, with 3D-printed brackets for the servo.

---

## 2. System Architecture

### 2.1 Block diagram

```
┌─────────────────────────── Raspberry Pi 5 ───────────────────────────┐
│                                                                       │
│   USB Webcam ───▶ V4L2 (/dev/video0, MJPG, 640×480 @ 15fps)           │
│                       │                                               │
│                       ▼                                               │
│                 cv2.VideoCapture ──▶ FrameHub (threading.Condition)   │
│                                          │                            │
│           ┌──────────────────────────────┼───────────────────────┐    │
│           ▼                              ▼                       ▼    │
│   Detector thread             Flask /stream.mjpeg          Recorder   │
│   (MediaPipe + pyzbar)        (passthrough JPEG)           (ring buf  │
│           │                       │                        → ffmpeg)  │
│           ▼                       ▼                                   │
│      SQLite user DB         Admin browser (LAN)                       │
│           │                                                           │
│           ▼                                                           │
│   pyserial /dev/ttyUSB0 @ 115200 ◀────────────── esptool.py @ 921600  │
└──────────────────┬────────────────────────────────────────────────────┘
                   │ USB cable (1 sợi)
┌──────────────────┴───────────────────────────────────────────────────┐
│                          ESP32-WROOM-32 DevKit                       │
│                                                                      │
│   CP2102 ─── UART0 (TX/RX) ─── USB-CDC                               │
│                                                                      │
│   FreeRTOS tasks: rfid · uart_link · servo · sensor · lcd · buzzer   │
│   NVS: authorized RFID UIDs + config                                 │
│   Wi-Fi: DISABLED                                                    │
│                                                                      │
│   Peripherals (via carrier PCB headers):                             │
│     RC522 (SPI) — LCD 20×4 (I2C) — HC-SR04 — SG90 servo — Buzzer     │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2 Power

- **Pi 5** has its own USB-C PD power supply (5 V / 5 A), independent of the ESP32 carrier.
- **ESP32 carrier** is fed from a **12 V / 2 A barrel jack**, stepped down by a buck converter (MP1584 or LM2596 module) to a 5 V rail. A linear regulator (AMS1117-3.3) then derives 3.3 V from 5 V for ESP32 and RC522.
- Ground is shared between Pi and ESP32 via the USB cable shield + signal ground.

Estimated current draw (peak):
- 3V3 rail: ESP32 (120 mA) + RC522 (30 mA) ≈ **150 mA**
- 5V rail: LCD+backlight (50 mA) + HC-SR04 (15 mA) + SG90 inrush (500 mA) + buzzer (30 mA) ≈ **600 mA peak**
- 12V input @ ~85% buck efficiency ≈ **300 mA peak** — well within 2 A adapter rating.

A 470 µF electrolytic capacitor should be placed on the 5 V rail near the servo connector to absorb servo current spikes.

---

## 3. Video Streaming Pipeline (Pi side)

### 3.1 Camera

**USB UVC webcam** (e.g., Logitech C270 entry-level, or C920 if 1080p is wanted). Plugged into a Pi 5 USB 3.0 port. Pi Camera Module 3 (CSI ribbon) was considered and rejected because USB is easier to mount on the demo stand and the user already has a USB webcam.

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

- Physical: USB cable, Pi USB-A → DevKit micro-USB.
- Pi side: `/dev/ttyUSB0` (CP2102) at 115200 baud, 8N1, no flow control. (USB-CDC ignores baud rate at the USB layer; 115200 is the configured app rate for symmetry.)
- ESP32 side: UART0 (GPIO 1 TX, GPIO 3 RX), connected internally to CP2102 on the DevKit.
- The same physical cable is used for `esptool.py write_flash` at 921600 baud during firmware updates. Application comm is paused (Pi-side software closes the port) while flashing.

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

## 5. ESP32 Pin Assignment

Module: ESP32-WROOM-32 (classic). DevKit form-factor: **DOIT V1 30-pin** (confirmed 2026-05-22). Because the 30-pin variant does **not** expose IO18/19/21/22/23 on its headers, the default VSPI and I2C pin assignments cannot be used. Peripherals are remapped via the ESP32 GPIO matrix (any GPIO can be assigned to SPI/I2C in software).

| GPIO | Direction | Peripheral | Notes |
| --- | --- | --- | --- |
| 1 | OUT (UART0 TX) | USB-CDC TX | Reserved. Pi link + flash + debug. |
| 3 | IN (UART0 RX) | USB-CDC RX | Reserved. |
| 2 | OUT (strap) | Onboard status LED | Strap: must not be pulled HIGH at boot. Driver writes HIGH/LOW after boot. |
| 14 | OUT | RC522 SCK | Remapped VSPI. |
| 13 | OUT | RC522 MOSI | Remapped VSPI. |
| 35 | IN only | RC522 MISO | Input-only pin; MISO is always input from RC522 → ESP32, so this is correct. No internal pull-up — RC522 module drives push-pull. |
| 15 | OUT (strap) | RC522 CS | Strap: HIGH at boot. RC522 CS idle HIGH ⇒ compatible. |
| 4 | OUT | RC522 RST | Active LOW; pull HIGH during operation. |
| 16 | IN | RC522 IRQ | Optional; FALLING edge interrupt. |
| 32 | I/O | LCD I2C SDA | Remapped I2C. 4.7 kΩ pull-up to **3.3 V** (not 5 V — see §5.2). |
| 33 | OUT | LCD I2C SCL | Remapped I2C. 4.7 kΩ pull-up to **3.3 V**. |
| 25 | OUT | HC-SR04 TRIG | 10 µs pulse. 3.3 V output usually triggers HC-SR04 OK; add BS170 level shifter if marginal. |
| 34 | IN only | HC-SR04 ECHO | **Voltage divider mandatory**: R1=1 kΩ in series, R2=2 kΩ to GND → 5 V echo becomes ~3.3 V at GPIO 34. |
| 26 | OUT | Servo SG90 PWM | LEDC channel 0, 50 Hz, 1–2 ms pulse. 3.3 V exceeds SG90 input threshold. |
| 27 | OUT (digital) | Active buzzer | Plain GPIO HIGH/LOW; buzzer has internal oscillator. Drive via NPN 2N3904 + 1 kΩ base resistor (buzzer current ~25 mA > GPIO 12 mA safe limit). |
| 6–11 | — | **DO NOT USE** | Connected to internal SPI flash. Not exposed on the 30-pin header. |
| 12 | — | **DO NOT USE** | Strap pin: must be LOW at boot for 3.3 V flash voltage. Leaving floating is safest. |
| 17 | — | Unused / spare | Free for future use; bring out to expansion header. |
| 5 | — | Unused / spare | Strap (HIGH at boot). Free; bring out to expansion header. |
| 36, 39 | IN only | Unused / spare | ADC1 capable; bring out to expansion header. |

Free GPIOs reserved for the 6-pin expansion header: 17, 5, 36, 39 (plus +3V3 and GND). GPIO 12 is excluded because of its strap requirement.

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

Barrier-style demo gate. Two posts flank a 60 mm lane; an 80 mm arm rotates 90° between horizontal (CLOSED) and vertical (OPEN). Overall footprint ~200 × 100 mm, height ~100 mm including the camera stand omitted (camera stand is separate, ~250 mm tall).

### 6.2 Parts list

| Part | Dimensions (mm) | Material | Notes |
| --- | --- | --- | --- |
| Base box | 200 × 100 × 40 | MDF 3 mm, laser-cut, finger joints | Houses Pi 5 + ESP32 carrier PCB + buck + cabling. |
| Left post (servo) | 30 × 30 × 60 | MDF 3 mm (6-panel hollow) | SG90 mounted horizontally; horn exits right face. |
| Right post (rest) | 30 × 30 × 60 | MDF 3 mm (6-panel) | Top has a notched rest pad with foam liner. |
| Arm | 80 × 8 × 3 | Balsa or acrylic | Painted red/yellow stripes; vit M2 to servo horn + glue. |
| Servo bracket | ~25 × 25 × 25 | 3D printed PLA | Two M3 holes for SG90 ears; bolts down to inside of left post. |
| Webcam stand | dia 8 × 250 + base 80 × 80 | Wooden dowel + MDF base | Webcam clips on top, faces lane at ~30° downward. |
| Front panel of base | 200 × 40 | MDF 3 mm with cutouts | LCD 98 × 24, RC522 60 × 40, HC-SR04 2 × Ø16, LED Ø3, buzzer Ø8. |
| Back panel of base | 200 × 40 | MDF 3 mm with cutouts | DC barrel jack Ø8, Pi USB-C 14 × 6, 4 ventilation slots. |

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

---

## 8. Out of scope (deferred to future plans)

- Firmware implementation for ESP32 (FreeRTOS task design, ArduinoJson integration, NVS schema). → next plan.
- Pi 5 application code (Flask routes, SQLite schema, face encoding storage, ffmpeg invocation). → next plan.
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

---

*End of design doc.*
