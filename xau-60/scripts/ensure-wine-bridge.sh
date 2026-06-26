#!/usr/bin/env bash
# Start mt5linux bridge in the background if Wine mode is enabled and it is not running.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

load_wine_env() {
  if [[ ! -f .env ]]; then
    return 1
  fi
  while IFS= read -r line; do
    [[ "$line" =~ ^MT5_WINE_ ]] || continue
    key="${line%%=*}"
    value="${line#*=}"
    value="${value%\"}"
    value="${value#\"}"
    export "$key=$value"
  done < <(grep -E '^MT5_WINE_' .env)
}

load_wine_env || true

if [[ "${MT5_WINE_ENABLED:-false}" != "true" ]]; then
  exit 0
fi

PORT="${MT5_WINE_PORT:-18812}"

if .venv/bin/python -c "
import socket, sys
s = socket.socket()
s.settimeout(2)
try:
    s.connect(('127.0.0.1', int(sys.argv[1])))
except OSError:
    sys.exit(1)
finally:
    s.close()
" "$PORT" 2>/dev/null; then
  echo "Wine MT5 bridge already running on port $PORT"
  exit 0
fi

echo "Starting Wine MT5 bridge in background on port $PORT..."
mkdir -p logs

# shellcheck disable=SC2086
"$ROOT/scripts/start-wine-mt5linux.sh" --daemon

sleep 2

if .venv/bin/python scripts/check-wine-mt5.py 2>/dev/null | grep -q "RPyC server is reachable"; then
  echo "Wine MT5 bridge is up."
  exit 0
fi

echo "Bridge start attempted. If dashboard still shows an error:"
echo "  1) Open MT5 in Wine (logged into BlackBull)"
echo "  2) Run: ./scripts/start-wine-mt5linux.sh"
echo "  3) Check: tail -f logs/wine-bridge.log"
exit 0
