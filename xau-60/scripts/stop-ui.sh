#!/usr/bin/env bash
# Stop XAU-60 Streamlit UI on port 8020
set -euo pipefail

PORT=8020

echo "Stopping XAU-60 UI on port ${PORT}..."

if command -v fuser >/dev/null 2>&1; then
  fuser -k "${PORT}/tcp" 2>/dev/null || true
fi

if command -v lsof >/dev/null 2>&1; then
  PIDS=$(lsof -t -i:"${PORT}" 2>/dev/null || true)
  if [[ -n "${PIDS}" ]]; then
    kill ${PIDS} 2>/dev/null || true
    sleep 1
    kill -9 ${PIDS} 2>/dev/null || true
  fi
fi

pkill -f "streamlit run ui/app.py" 2>/dev/null || true

if ss -tln 2>/dev/null | grep -q ":${PORT} "; then
  echo "Port ${PORT} still in use. Run: ss -tlnp | grep ${PORT}"
  exit 1
fi

echo "Port ${PORT} is free."
