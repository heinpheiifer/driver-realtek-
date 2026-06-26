#!/usr/bin/env bash
# Start mt5linux bridge in the background if Wine mode is enabled and it is not running.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TMUX_SESSION="${XAU60_WINE_TMUX_SESSION:-xau60-wine-bridge}"

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

port_open() {
  local port="${1:-18812}"
  (echo >/dev/tcp/127.0.0.1/"$port") >/dev/null 2>&1
}

bridge_alive() {
  local port="${1:-18812}"
  [[ -x .venv/bin/python ]] || return 1
  .venv/bin/python -c "
import socket, sys
s = socket.socket()
s.settimeout(2)
try:
    s.connect(('127.0.0.1', int(sys.argv[1])))
except OSError:
    sys.exit(1)
finally:
    s.close()
" "$port" 2>/dev/null
}

load_wine_env || true

if [[ "${MT5_WINE_ENABLED:-false}" != "true" ]]; then
  exit 0
fi

PORT="${MT5_WINE_PORT:-18812}"

if bridge_alive "$PORT"; then
  echo "Wine MT5 bridge already running on port $PORT"
  exit 0
fi

if port_open "$PORT"; then
  echo "Port $PORT busy but bridge not responding — run ./scripts/stop-wine-mt5linux.sh"
  "$ROOT/scripts/stop-wine-mt5linux.sh" || true
  sleep 1
fi

echo "Starting Wine MT5 bridge on port $PORT..."
mkdir -p logs

# Wine embeddable Python crashes with nohup (WinError 6). Use tmux when available.
if command -v tmux >/dev/null 2>&1; then
  if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true
    sleep 1
  fi
  tmux new-session -d -s "$TMUX_SESSION" -c "$ROOT" \
    "./scripts/start-wine-mt5linux.sh"
  echo "Bridge starting in tmux session: $TMUX_SESSION"
  echo "  Attach: tmux attach -t $TMUX_SESSION"
  echo "  Logs:   tmux capture-pane -pt $TMUX_SESSION -S -20"
else
  warn_msg="tmux not installed — install with: sudo apt install tmux"
  echo "$warn_msg"
  echo ""
  echo "Run the bridge manually in another terminal (required):"
  echo "  ./scripts/start-wine-mt5linux.sh"
  exit 1
fi

for _ in 1 2 3 4 5 6 7 8 9 10; do
  sleep 1
  if bridge_alive "$PORT"; then
    echo "Wine MT5 bridge is up on port $PORT"
    exit 0
  fi
done

echo "Bridge not responding yet."
echo "  1) Open MT5 in Wine (517035 @ BlackBullMarkets-Live)"
echo "  2) tmux attach -t $TMUX_SESSION   # see errors"
echo "  3) ./scripts/debug-wine-mt5.sh"
exit 1
