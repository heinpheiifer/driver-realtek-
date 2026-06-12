#!/usr/bin/env bash
# Stop anything listening on Open Trader port (default 8010).
set -euo pipefail

PORT="${PORT:-8010}"

echo "==> Stopping Open Trader on port ${PORT} ..."

pkill -f "uvicorn opentrader.main" 2>/dev/null || true
pkill -f "uvicorn opentrade.main" 2>/dev/null || true
sleep 1

if command -v fuser >/dev/null; then
  fuser -k "${PORT}/tcp" 2>/dev/null || true
fi
if command -v lsof >/dev/null; then
  lsof -ti ":${PORT}" 2>/dev/null | xargs -r kill -9 2>/dev/null || true
fi

for _ in $(seq 1 10); do
  if command -v ss >/dev/null && ! ss -ltn "sport = :${PORT}" 2>/dev/null | grep -q LISTEN; then
    echo "==> Port ${PORT} is free."
    exit 0
  fi
  sleep 1
done

echo "ERROR: Port ${PORT} still in use."
if command -v ss >/dev/null; then
  ss -ltnp "sport = :${PORT}" 2>/dev/null || true
fi
echo "Try: kill -9 <PID>   then   FORCE=1 bash run.sh"
exit 1
