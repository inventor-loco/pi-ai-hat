#!/bin/bash
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "Run as root: sudo bash start.sh"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/web_env"
PID_FILE="/tmp/pi-ai-hat.pids"
LOG_DIR="$SCRIPT_DIR/logs"

# Sanity check — venv must exist (run install.sh first)
if [ ! -f "$VENV_DIR/bin/python" ]; then
  echo "Virtual environment not found at $VENV_DIR."
  echo "Run install first: sudo bash $SCRIPT_DIR/install.sh"
  exit 1
fi

# Bail if already running
if [ -f "$PID_FILE" ]; then
  echo "Services appear to be running already (found $PID_FILE)."
  echo "Run 'sudo bash stop.sh' first, or delete $PID_FILE if stale."
  exit 1
fi

# If systemd is managing the services, stop them so ports are free.
for svc in hailo-daemon pi-ai-hat-web; do
  if systemctl is-active --quiet "$svc" 2>/dev/null; then
    echo "Stopping systemd unit $svc before starting in dev mode..."
    systemctl stop "$svc"
  fi
done

mkdir -p "$LOG_DIR"

echo "Starting hailo daemon..."
/usr/bin/python3 "$SCRIPT_DIR/hailo_daemon.py" \
  >"$LOG_DIR/hailo_daemon.log" 2>&1 &
DAEMON_PID=$!
echo "  PID $DAEMON_PID  →  $LOG_DIR/hailo_daemon.log"

# Give the daemon a moment to bind its port before the server tries to reach it.
sleep 2

echo "Starting web server..."
"$VENV_DIR/bin/python" "$SCRIPT_DIR/server.py" \
  >"$LOG_DIR/server.log" 2>&1 &
SERVER_PID=$!
echo "  PID $SERVER_PID  →  $LOG_DIR/server.log"

printf "%s %s\n" "$DAEMON_PID" "$SERVER_PID" > "$PID_FILE"

echo ""
echo "Both services are running."
echo "  Tail logs : tail -f $LOG_DIR/hailo_daemon.log $LOG_DIR/server.log"
echo "  Stop      : sudo bash $SCRIPT_DIR/stop.sh"
