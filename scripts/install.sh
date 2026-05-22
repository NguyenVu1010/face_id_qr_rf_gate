#!/usr/bin/env bash
set -euo pipefail

# Run from repo root: sudo bash scripts/install.sh

# 1. apt deps
sudo apt update
sudo apt install -y \
    python3 python3-venv \
    python3-opencv python3-dlib python3-mediapipe \
    libzbar0 ffmpeg sqlite3 v4l-utils curl

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

# 3. code
sudo rsync -a --delete \
    --exclude=.git --exclude=tests --exclude=__pycache__ --exclude=.venv \
    ./ /opt/smart-gate/

# 4. venv (visible to apt python packages)
sudo python3 -m venv --system-site-packages /opt/smart-gate/.venv
sudo /opt/smart-gate/.venv/bin/pip install --upgrade pip
sudo /opt/smart-gate/.venv/bin/pip install -r /opt/smart-gate/requirements.txt
sudo chown -R smart-gate:smart-gate /opt/smart-gate

# 5. config (don't overwrite)
if [ ! -f /etc/smart-gate/config.toml ]; then
    sudo install -o smart-gate -g smart-gate -m 0644 \
        packaging/config.default.toml /etc/smart-gate/config.toml
fi

# 6. download front-end vendor assets (replace placeholders)
sudo curl -fsSL https://unpkg.com/htmx.org@1.9.10/dist/htmx.min.js \
    -o /opt/smart-gate/smart_gate/web/static/htmx.min.js
sudo curl -fsSL https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css \
    -o /opt/smart-gate/smart_gate/web/static/pico.min.css
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
