#!/usr/bin/env bash
# Stop any running OpenTrader/OpenTrade server and start fresh on port 8010.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Stopping existing OpenTrader/OpenTrade processes ..."
pkill -f "uvicorn opentrader.main" 2>/dev/null || true
pkill -f "uvicorn opentrade.main" 2>/dev/null || true
sleep 1

PORT="${PORT:-8010}"
if command -v ss >/dev/null && ss -ltn "sport = :${PORT}" 2>/dev/null | grep -q LISTEN; then
  echo "Port ${PORT} still in use. Try:"
  echo "  ss -ltnp | grep :${PORT}"
  echo "  kill <PID>"
  exit 1
fi

echo "==> Starting fresh ..."
exec bash install_and_run.sh
