#!/usr/bin/env bash
set -euo pipefail

# Run from repo root: sudo bash scripts/install.sh

# 1. apt deps
# Notes:
# - Trixie renamed libzbar0 → libzbar0t64; we try both, ignore failure.
# - python3-dlib and python3-mediapipe are dropped: dlib is pip-built below
#   (no apt package on Trixie), and mediapipe has no Python 3.13 wheel — the
#   detector falls back to face_recognition's HOG path automatically.
sudo apt update
sudo apt install -y \
    python3 python3-venv python3-pip python3-dev \
    python3-opencv python3-numpy \
    python3-flask python3-jinja2 python3-serial python3-qrcode \
    ffmpeg sqlite3 v4l-utils curl \
    build-essential cmake pkg-config \
    libopenblas-dev liblapack-dev libboost-python-dev libx11-dev
sudo apt install -y libzbar0t64 || sudo apt install -y libzbar0

# 2. service user + dirs
sudo adduser --system --group --no-create-home smart-gate || true
sudo usermod -aG video,dialout smart-gate
sudo install -d -o smart-gate -g smart-gate \
    /opt/smart-gate \
    /etc/smart-gate \
    /var/lib/smart-gate \
    /var/lib/smart-gate/clips \
    /var/lib/smart-gate/qr \
    /var/log/smart-gate

# 3. code (preserve previously-downloaded vendor assets in static/)
sudo rsync -a --delete \
    --exclude=.git --exclude=tests --exclude=__pycache__ --exclude=.venv \
    --exclude=.claude --exclude=.pytest_cache --exclude=data \
    --exclude='smart_gate/web/static/htmx.min.js' \
    --exclude='smart_gate/web/static/pico.min.css' \
    ./ /opt/smart-gate/

# 4. venv (visible to apt python packages)
# Pip installs only what apt does not cover. flask/jinja2/qrcode/pyserial/
# numpy/opencv come from apt via --system-site-packages. dlib builds from
# source via pip (≈ 20–40 min on Pi 4); pyzbar is a pure-Python wrapper.
# We point pip's cache at the invoking user's cache dir so a previously built
# dlib wheel can be reused (avoids a second 30-min build if the user already
# set up a dev venv at $HOME/smart_gate).
INVOKING_HOME="${HOME:-/root}"
if [ -n "${SUDO_USER:-}" ]; then
    INVOKING_HOME="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
fi
PIP_CACHE_DIR="$INVOKING_HOME/.cache/pip"
sudo python3 -m venv --system-site-packages /opt/smart-gate/.venv
sudo PIP_CACHE_DIR="$PIP_CACHE_DIR" /opt/smart-gate/.venv/bin/pip install \
    --upgrade "pip" "setuptools<81" "wheel"
sudo PIP_CACHE_DIR="$PIP_CACHE_DIR" /opt/smart-gate/.venv/bin/pip install \
    dlib face_recognition pyzbar
sudo chown -R smart-gate:smart-gate /opt/smart-gate

# 5. config (don't overwrite)
if [ ! -f /etc/smart-gate/config.toml ]; then
    sudo install -o smart-gate -g smart-gate -m 0644 \
        packaging/config.default.toml /etc/smart-gate/config.toml
fi

# 6. download front-end vendor assets (only if missing or tiny placeholder)
HTMX_FILE=/opt/smart-gate/smart_gate/web/static/htmx.min.js
PICO_FILE=/opt/smart-gate/smart_gate/web/static/pico.min.css
HTMX_SIZE=$(stat -c%s "$HTMX_FILE" 2>/dev/null || echo 0)
PICO_SIZE=$(stat -c%s "$PICO_FILE" 2>/dev/null || echo 0)
if [ "$HTMX_SIZE" -lt 10000 ]; then
    sudo curl -fsSL https://unpkg.com/htmx.org@1.9.10/dist/htmx.min.js -o "$HTMX_FILE"
    echo "  downloaded htmx.min.js"
else
    echo "  htmx.min.js already present ($HTMX_SIZE bytes), skipping download"
fi
if [ "$PICO_SIZE" -lt 10000 ]; then
    sudo curl -fsSL https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css -o "$PICO_FILE"
    echo "  downloaded pico.min.css"
else
    echo "  pico.min.css already present ($PICO_SIZE bytes), skipping download"
fi
sudo chown smart-gate:smart-gate /opt/smart-gate/smart_gate/web/static/*

# 7. systemd
sudo install -m 0644 packaging/smart-gate.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now smart-gate

# 8. initial migration
sudo -u smart-gate /opt/smart-gate/.venv/bin/python -m smart_gate.cli \
    --config /etc/smart-gate/config.toml db migrate

echo "smart_gate installed. Check: sudo systemctl status smart-gate"
echo "Logs:                       sudo journalctl -u smart-gate -f"
