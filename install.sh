#!/bin/bash
set -euo pipefail

# Must run as root — needed to install packages, write systemd units, and configure the hotspot.
if [ "$EUID" -ne 0 ]; then
  echo "Run as root: sudo bash install.sh"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/web_env"
SERVICE_USER="${SUDO_USER:-pi}"

echo "=== pi-ai-hat install ==="
echo "Project dir : $SCRIPT_DIR"
echo "Venv        : $VENV_DIR"
echo ""

# ---------------------------------------------------------------------------
# 1. System dependencies
# ---------------------------------------------------------------------------
echo "[1/6] Installing system packages..."
apt-get update -qq
apt-get install -y python3-venv python3-pip openssl

# ---------------------------------------------------------------------------
# 2. Python virtual environment for the web server
# ---------------------------------------------------------------------------
echo "[2/6] Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
  echo "  Created $VENV_DIR"
else
  echo "  Already exists, skipping creation."
fi

echo "  Installing requirements..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"

# ---------------------------------------------------------------------------
# 3. SSL certificate (self-signed, for HTTPS on port 443)
# ---------------------------------------------------------------------------
echo "[3/6] Checking SSL certificate..."
if [ ! -f "$SCRIPT_DIR/cert.pem" ] || [ ! -f "$SCRIPT_DIR/key.pem" ]; then
  echo "  Generating self-signed certificate..."
  openssl req -x509 -newkey rsa:2048 -nodes \
    -out "$SCRIPT_DIR/cert.pem" \
    -keyout "$SCRIPT_DIR/key.pem" \
    -days 3650 \
    -subj "/CN=hailocam" 2>/dev/null
  echo "  Done."
else
  echo "  Certificate already exists, skipping."
fi

# ---------------------------------------------------------------------------
# 4. Models directory
# ---------------------------------------------------------------------------
mkdir -p "$SCRIPT_DIR/models"

# ---------------------------------------------------------------------------
# 5. Wi-Fi hotspot (NetworkManager captive portal AP)
# ---------------------------------------------------------------------------
echo "[5/6] Configuring Wi-Fi hotspot..."
bash "$SCRIPT_DIR/setup_hotspot.sh"

# ---------------------------------------------------------------------------
# 6. Systemd service units
# ---------------------------------------------------------------------------
echo "[6/6] Installing systemd service units..."

# hailo-daemon — runs under root (needs Hailo hardware access)
cat > /etc/systemd/system/hailo-daemon.service <<EOF
[Unit]
Description=Hailo AI Inference Daemon
After=network.target

[Service]
Type=simple
WorkingDirectory=$SCRIPT_DIR
ExecStart=/usr/bin/python3 $SCRIPT_DIR/hailo_daemon.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# pi-ai-hat-web — FastAPI server, depends on the daemon being up
cat > /etc/systemd/system/pi-ai-hat-web.service <<EOF
[Unit]
Description=pi-ai-hat Web Server
After=network.target NetworkManager.service hailo-daemon.service
Requires=hailo-daemon.service

[Service]
Type=simple
WorkingDirectory=$SCRIPT_DIR
ExecStartPre=-/usr/bin/nmcli connection up "Hailo AI Cam"
ExecStart=$VENV_DIR/bin/python $SCRIPT_DIR/server.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable hailo-daemon.service pi-ai-hat-web.service

echo ""
echo "=== Install complete ==="
echo ""
echo "Services are enabled and will start automatically on next boot."
echo "To start them right now:   sudo bash $SCRIPT_DIR/start.sh"
echo "To check status:           systemctl status hailo-daemon pi-ai-hat-web"
echo "To tail logs:              journalctl -fu hailo-daemon -fu pi-ai-hat-web"
