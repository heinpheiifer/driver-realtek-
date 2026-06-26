#!/usr/bin/env bash
# Start mt5linux RPyC server inside Wine (same laptop as XAU-60 UI).
#
# Prerequisites:
#   - MT5 terminal running in Wine (BlackBull logged in)
#   - Windows Python in Wine with: pip install MetaTrader5 mt5linux
#
# Usage:
#   ./scripts/start-wine-mt5linux.sh
#   ./scripts/start-wine-mt5linux.sh --restart   # kill stale bridge first
#   MT5_WINE_PYTHON="wine /path/to/python.exe" ./scripts/start-wine-mt5linux.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RESTART=false
DAEMON=false
for arg in "$@"; do
  case "$arg" in
    --restart|-r) RESTART=true ;;
    --daemon|-d) DAEMON=true ;;
  esac
done

if [[ -f .env ]]; then
  while IFS= read -r line; do
    [[ "$line" =~ ^MT5_WINE_ ]] || continue
    key="${line%%=*}"
    value="${line#*=}"
    value="${value%\"}"
    value="${value#\"}"
    export "$key=$value"
  done < <(grep -E '^MT5_WINE_' .env)
fi

# Host the Linux app connects to (client side)
CLIENT_HOST="${MT5_WINE_HOST:-localhost}"
# Host the RPyC server binds inside Wine (keep on loopback)
BIND_HOST="${MT5_WINE_BIND_HOST:-127.0.0.1}"
PORT="${MT5_WINE_PORT:-18812}"
WINE_PYTHON="${MT5_WINE_PYTHON:-wine python}"

WINE_PYTHON="${WINE_PYTHON//\$HOME/$HOME}"
read -ra WINE_PY_CMD <<< "$WINE_PYTHON"

port_open() {
  (echo >/dev/tcp/127.0.0.1/"$PORT") >/dev/null 2>&1 \
    || (echo >/dev/tcp/localhost/"$PORT") >/dev/null 2>&1
}

bridge_alive() {
  if [[ -x .venv/bin/python ]]; then
    .venv/bin/python -c "
import socket, sys
s = socket.socket()
s.settimeout(2)
try:
    s.connect(('127.0.0.1', int(sys.argv[1])))
    sys.exit(0)
except OSError:
    sys.exit(1)
finally:
    s.close()
" "$PORT" 2>/dev/null
    return $?
  fi
  port_open
}

echo "==> XAU-60 Wine MT5 bridge (mt5linux RPyC)"
echo "    Bind: $BIND_HOST  Port: $PORT  (Linux connects via $CLIENT_HOST)"
echo ""

if port_open; then
  if [[ "$RESTART" == true ]]; then
    echo "Port $PORT in use — restarting bridge..."
    "$ROOT/scripts/stop-wine-mt5linux.sh" || true
  elif bridge_alive; then
    echo "Bridge is already running on port $PORT."
    echo "  Test:  .venv/bin/python scripts/check-wine-mt5.py"
    echo "  Stop:  ./scripts/stop-wine-mt5linux.sh"
    echo "  Restart: ./scripts/start-wine-mt5linux.sh --restart"
    exit 0
  else
    echo "Port $PORT is blocked but bridge is not responding."
    echo "Stopping stale process..."
    "$ROOT/scripts/stop-wine-mt5linux.sh" || true
  fi
fi

echo "Before continuing:"
echo "  1. Open MetaTrader 5 in Wine and log into BlackBull"
echo "  2. Wine Python needs: pip install MetaTrader5 mt5linux"
echo ""
echo "Linux .env:"
echo "  MT5_WINE_ENABLED=true"
echo "  MT5_WINE_HOST=localhost"
echo "  MT5_WINE_PORT=$PORT"
echo ""

if [[ "$DAEMON" == true ]]; then
  LOG="$ROOT/logs/wine-bridge.log"
  PIDFILE="$ROOT/logs/wine-bridge.pid"
  mkdir -p "$ROOT/logs"
  echo "Logging to $LOG"
  nohup "${WINE_PY_CMD[@]}" -m mt5linux --host "$BIND_HOST" -p "$PORT" >>"$LOG" 2>&1 &
  echo $! > "$PIDFILE"
  echo "Wine bridge started in background (pid $(cat "$PIDFILE"))."
  exit 0
fi

exec "${WINE_PY_CMD[@]}" -m mt5linux --host "$BIND_HOST" -p "$PORT"
