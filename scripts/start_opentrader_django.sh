#!/usr/bin/env bash
# Start original OpenTrader Django backend (MT5 / BlackBull data API)
#
# Usage:
#   bash scripts/start_opentrader_django.sh /home/heinz/OpenTrader
#   bash scripts/start_opentrader_django.sh /home/heinz/OpenTrader /home/heinz/opentrade-app
#
set -euo pipefail

CHART_ROOT="${1:-/home/heinz/OpenTrader}"
ENGINE_DIR="${2:-/home/heinz/opentrade-app}"
PORT="${DJANGO_PORT:-8000}"
PID_FILE="${CHART_ROOT}/.opentrader_django.pid"
LOG_FILE="${CHART_ROOT}/.opentrader_django.log"

_find_manage() {
  for dir in "$CHART_ROOT" "$CHART_ROOT/backend" "$CHART_ROOT/server" "$CHART_ROOT/api"; do
    [[ -f "$dir/manage.py" ]] && echo "$dir" && return 0
  done
  return 1
}

_set_engine_env() {
  local key="$1" val="$2"
  local env_file="$ENGINE_DIR/.env"
  mkdir -p "$ENGINE_DIR"
  touch "$env_file"
  if grep -q "^${key}=" "$env_file" 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$env_file"
  else
    echo "${key}=${val}" >> "$env_file"
  fi
}

MANAGE_DIR="$(_find_manage || true)"
if [[ -z "$MANAGE_DIR" ]]; then
  echo "No Django manage.py in $CHART_ROOT"
  echo ""
  echo "Checked:"
  echo "  $CHART_ROOT/manage.py"
  echo "  $CHART_ROOT/backend/manage.py"
  echo "  $CHART_ROOT/server/manage.py"
  echo ""
  echo "OpenTrader may use a different backend. Try:"
  echo "  find $CHART_ROOT -name manage.py"
  echo "  bash scripts/start_blackbull_bridge.sh $ENGINE_DIR"
  exit 1
fi

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Django already running (PID $(cat "$PID_FILE")) on http://127.0.0.1:${PORT}"
else
  echo "==> Starting Django: $MANAGE_DIR"
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
  sleep 3
  echo "==> PID $(cat "$PID_FILE") — log: $LOG_FILE"
fi

BASE="http://127.0.0.1:${PORT}"
OK=0
for path in \
  "/api/history/?symbol=XRPUSD&interval=1m&range=1d&source=blackbull" \
  "/api/mt5/status/" \
  "/api/health" \
  "/api/candles?symbol=XRPUSD&timeframe=M1"; do
  if curl -sf "${BASE}${path}" >/dev/null 2>&1; then
    echo "✓ ${BASE}${path}"
    OK=1
  fi
done

if [[ "$OK" -eq 0 ]]; then
  echo ""
  echo "Django is running but API not responding yet. Check log:"
  echo "  tail -30 $LOG_FILE"
  echo ""
  echo "Common fixes:"
  echo "  cd $MANAGE_DIR && pip install -r requirements.txt"
  echo "  cd $MANAGE_DIR && python manage.py migrate"
  exit 1
fi

_set_engine_env "OPENTRADER_BACKEND_URL" "http://127.0.0.1:${PORT}"
_set_engine_env "OPENTRADER_USE_OLD_UI" "1"
_set_engine_env "MT5_AUTO_SYNC" "0"

echo ""
echo "==> Configured $ENGINE_DIR/.env with OPENTRADER_BACKEND_URL"
echo ""
echo "Restart chart engine:"
echo "  cd $ENGINE_DIR"
echo "  bash scripts/stop_opentrader.sh"
echo "  FORCE=1 bash run.sh"
echo ""
echo "Test via chart server (proxied to Django):"
echo "  curl -s 'http://127.0.0.1:8010/api/history/?symbol=XRPUSD&interval=1m&range=1d&source=blackbull' | head -c 200"
