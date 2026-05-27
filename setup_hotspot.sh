#!/bin/bash
set -euo pipefail

# Ensure we are running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run this script as root (sudo ./setup_hotspot.sh)"
  exit 1
fi

echo "Setting up Captive Portal and Wi-Fi Hotspot..."

# 1. Configure NetworkManager to use a custom dnsmasq config for the shared connection
mkdir -p /etc/NetworkManager/dnsmasq-shared.d
cat <<EOF > /etc/NetworkManager/dnsmasq-shared.d/captive_portal.conf
# Intercept all DNS queries and redirect them to the gateway IP (10.42.0.1)
address=/#/10.42.0.1
EOF

# 2. Restart NetworkManager to load the dnsmasq config
systemctl restart NetworkManager

# Wait a moment for NetworkManager to come back up
sleep 3

# 3. Create the hotspot connection
# We delete any existing hotspot profile with the same name to avoid conflicts
nmcli connection delete "Hailo AI Cam" 2>/dev/null || true

echo "Creating the Wi-Fi Hotspot..."
# Note: we assume the wi-fi interface is wlan0.
nmcli connection add type wifi ifname wlan0 con-name "Hailo AI Cam" autoconnect yes ssid "Hailo AI Cam"
nmcli connection modify "Hailo AI Cam" 802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared

echo "Activating the hotspot..."
nmcli connection up "Hailo AI Cam"

echo ""
echo "Success! The 'Hailo AI Cam' Wi-Fi network is now broadcasting."
echo "Any device connecting to it will be redirected to the web app (Captive Portal)."
