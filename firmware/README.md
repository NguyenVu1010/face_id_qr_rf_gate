# smart_gate ESP32 firmware

See `../docs/superpowers/specs/2026-05-22-esp32-firmware-design.md` for the design.

## Build

```bash
pio run
```

## Flash

```bash
# Pi pyserial app must release /dev/ttyUSB0 first.
pio run -t upload
```

## Monitor

```bash
pio device monitor
```

Pin map and acceptance test scenarios are added in Task 11.
