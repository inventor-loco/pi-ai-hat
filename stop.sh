#!/bin/bash
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "Run as root: sudo bash stop.sh"
  exit 1
fi

PID_FILE="/tmp/pi-ai-hat.pids"

if [ -f "$PID_FILE" ]; then
  read -r DAEMON_PID SERVER_PID < "$PID_FILE"

  echo "Stopping web server (PID $SERVER_PID)..."
  kill "$SERVER_PID" 2>/dev/null && echo "  Sent SIGTERM." || echo "  Already gone."

  echo "Stopping hailo daemon (PID $DAEMON_PID)..."
  kill "$DAEMON_PID" 2>/dev/null && echo "  Sent SIGTERM." || echo "  Already gone."

  rm -f "$PID_FILE"
else
  echo "No PID file found — trying pkill by script name."
fi

# Belt-and-suspenders: catch any stragglers not tracked by the PID file.
pkill -f "hailo_daemon.py" 2>/dev/null && echo "  Killed stale hailo_daemon.py." || true
pkill -f "server.py"       2>/dev/null && echo "  Killed stale server.py."       || true

echo "Stopping hotspot..."
nmcli connection down "Hailo AI Cam" 2>/dev/null && echo "  Hotspot down." || echo "  Hotspot was not active."

echo "Done."
