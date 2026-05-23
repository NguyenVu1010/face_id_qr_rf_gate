# smart_gate (Pi 5 side)

See `docs/superpowers/specs/2026-05-22-pi-app-design.md` for design.

## Dev setup

```
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest tests/ -q
```

## Production install

```
sudo bash scripts/install.sh
```

## Pi GPIO UART setup (one-time, before first run)

The daemon talks to ESP32 over the Pi GPIO UART (`/dev/serial0`), not USB-CDC.
Before first run:

1. Disable Pi serial console:
   ```
   sudo raspi-config
   # Interface Options → Serial Port
   #   "Login shell over serial?" → NO
   #   "Serial port hardware enabled?" → YES
   sudo reboot
   ```
2. Verify the device exists and is readable:
   ```
   ls -l /dev/serial0    # should be a symlink to ttyAMA0 or ttyS0
   ```
3. Wire 3 Dupont leads between Pi GPIO header and ESP32 DevKit:
   - Pi pin **8** (BCM14, TX0) → ESP32 **GPIO 32** (UART1 RX)
   - Pi pin **10** (BCM15, RX0) ← ESP32 **GPIO 25** (UART1 TX)
   - Pi pin **6** (GND) ↔ ESP32 GND

4. Add the daemon user to `dialout` so it can open `/dev/serial0`:
   ```
   sudo usermod -aG dialout smart-gate
   ```

## Flashing ESP32 (must stop daemon)

Firmware flashing still needs a separate USB cable from the Pi to the DevKit
USB-C/micro-USB port. `esptool.py` needs DTR/RTS auto-reset which the GPIO
UART doesn't provide.

```
sudo systemctl stop smart-gate
# Plug USB cable Pi → DevKit (data + power OK while daemon is stopped; the
# servo isn't moving and Pi USB current budget is plenty for the no-load case)
esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 921600 write_flash 0x0 firmware.bin
# Unplug USB cable (or leave it for `pio device monitor` debug log)
sudo systemctl start smart-gate
```

After flashing, runtime traffic resumes over `/dev/serial0` (the GPIO UART).
The USB cable is optional while the daemon runs.

## Web admin smoke test (pre-merge)

With the daemon running and the ESP32 connected:

1. Open `http://<pi>:8080/`. Top bar shows green **LINK** pill + cap fps number + frame-age (< 1s). Stream `<img>` shows a placeholder until the camera publishes.
2. Click **⏵ Open gate** — gate opens, toast "Gate opening…". Click **⏹ Close gate** — toast "Gate closing…".
3. Click **+ Tạo user mới** → confirm dialog → enroll-result card appears with QR thumbnail + ⬇ Tải QR PNG button.
4. Trigger an authorized face match — within 2 s a new row appears at the top of Recent events.
5. Watch the gate badge cycle through `idle → opening → open → timeout_warn → closing → idle` over a 20s arc; `timeout_warn` should pulse.
6. Navigate to `/events`. Toggle the `face` filter pill — only face rows show. Clear filter, choose **denied** — only stranger rows show. Type "ali" in the user search — only alice rows. Pick "Last 7 days" period. Click `▶` on a row that has a clip — native `<dialog>` modal plays the mp4 + offers Download.
7. Navigate to `/users` — alice row visible with QR thumbnail + ⬇ download button. Counter shows "N enrolled".
8. Navigate to `/system` — four status cards green (LINK / CAP / DET / DISK), pretty-printed health JSON, two diag buttons. Click **Send ping** → modal opens with `ack_ms` integer. Click **Send cmd:status** → modal updates with the ESP32-side status payload. ESP32 log scrolls live, newest-first.
9. **Failure-mode walk:**
   - Unplug USB to ESP32. Within ~5 s:
     - Top bar LINK pill turns amber.
     - `link-banner` appears: "⚠ Link down — UART silent. Manual gate commands disabled."
     - `Open gate` → toast "Gate command failed".
     - `#sse-status` becomes "reconnecting…".
   - Replug USB. Within ~5 s: banner disappears, LINK turns green, SSE pill goes live; any ESP32 log lines emitted during the outage are replayed (uses `Last-Event-ID` resume).
10. **Pause / Clear** controls on the ESP32 log list work; capacity is bounded at 500 lines (oldest dropped).

If any step fails: `pytest tests/ -q --ignore=tests/unit/test_cli.py` should still be green; the bug is in templates/JS rather than backend.
