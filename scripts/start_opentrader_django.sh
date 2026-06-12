#!/usr/bin/env bash
# Start original OpenTrader Django backend (MT5 / BlackBull data API)
set -euo pipefail

CHART_ROOT="${1:-/home/heinz/OpenTrader}"
PORT="${DJANGO_PORT:-8000}"
PID_FILE="${CHART_ROOT}/.opentrader_django.pid"
LOG_FILE="${CHART_ROOT}/.opentrader_django.log"

_find_manage() {
  for dir in "$CHART_ROOT" "$CHART_ROOT/backend" "$CHART_ROOT/server" "$CHART_ROOT/api"; do
    [[ -f "$dir/manage.py" ]] && echo "$dir" && return 0
  done
  return 1
}

MANAGE_DIR="$(_find_manage || true)"
if [[ -z "$MANAGE_DIR" ]]; then
  echo "No Django manage.py in $CHART_ROOT — skip Django backend."
  echo "Use MT5 bridge instead: bash scripts/start_blackbull_bridge.sh"
  exit 0
fi

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Django backend already running (PID $(cat "$PID_FILE")) on :$PORT"
  exit 0
fi

echo "==> Starting OpenTrader Django backend: $MANAGE_DIR"
cd "$MANAGE_DIR"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
elif [[ -f venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

nohup python manage.py runserver "127.0.0.1:${PORT}" >>"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"
sleep 2

if curl -sf "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1 || \
   curl -sf "http://127.0.0.1:${PORT}/api/candles?symbol=XRPUSD&timeframe=M1" >/dev/null 2>&1; then
  echo "==> Django backend OK at http://127.0.0.1:${PORT}"
  echo "    Log: $LOG_FILE"
else
  echo "==> Django started (PID $(cat "$PID_FILE")) — check log if chart data fails:"
  echo "    tail -f $LOG_FILE"
fi
