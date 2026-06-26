#!/usr/bin/env bash
# Stop the mt5linux RPyC bridge (Wine Python on port 18812).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

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

PORT="${MT5_WINE_PORT:-18812}"

port_open() {
  (echo >/dev/tcp/127.0.0.1/"$PORT") >/dev/null 2>&1
}

echo "==> Stopping Wine MT5 bridge on port $PORT"

PIDFILE="$ROOT/logs/wine-bridge.pid"
if [[ -f "$PIDFILE" ]]; then
  pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
  fi
  rm -f "$PIDFILE"
fi

if command -v fuser >/dev/null 2>&1; then
  fuser -k "${PORT}/tcp" 2>/dev/null || true
fi

# Wine-side python / mt5linux
pkill -f "[m]t5linux" 2>/dev/null || true
pkill -f "python.exe.*mt5linux" 2>/dev/null || true

sleep 1

if port_open; then
  echo "WARNING: Port $PORT is still in use."
  echo "Try manually:"
  echo "  ss -tlnp | grep $PORT"
  echo "  kill <pid>"
  exit 1
fi

echo "Bridge stopped."
