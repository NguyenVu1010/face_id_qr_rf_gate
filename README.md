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

## Flashing ESP32 (must stop daemon)

```
sudo systemctl stop smart-gate
esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 921600 write_flash 0x0 firmware.bin
sudo systemctl start smart-gate
```
