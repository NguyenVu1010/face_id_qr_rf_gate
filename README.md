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
