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
  find "$CHART_ROOT" -maxdepth 4 -name manage.py -print -quit 2>/dev/null || true
}

_python() {
  if command -v python3 >/dev/null 2>&1; then
    echo python3
  else
    echo python
  fi
}

_http_code() {
  curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 --max-time 8 "$1" 2>/dev/null || echo "000"
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

_show_log_tail() {
  if [[ -f "$LOG_FILE" ]]; then
    echo ""
    echo "---- last 30 lines of $LOG_FILE ----"
    tail -30 "$LOG_FILE" || true
    echo "------------------------------------"
  fi
}

MANAGE_DIR="$(_find_manage || true)"
if [[ -z "$MANAGE_DIR" || ! -f "$MANAGE_DIR/manage.py" ]]; then
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

PY="$(_python)"

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
  elif [[ -f "$ENGINE_DIR/.venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$ENGINE_DIR/.venv/bin/activate"
  fi

  : >"$LOG_FILE"
  nohup "$PY" manage.py runserver "127.0.0.1:${PORT}" >>"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  echo "==> PID $(cat "$PID_FILE") — log: $LOG_FILE"
fi

BASE="http://127.0.0.1:${PORT}"
PATHS=(
  "/"
  "/api/health"
  "/api/mt5/status/"
  "/api/history/?symbol=XRPUSD&interval=1m&range=1d&source=blackbull"
  "/api/candles?symbol=XRPUSD&timeframe=M1"
  "/admin/"
)

echo ""
echo "Waiting for Django on ${BASE} ..."
UP=0
DATA_OK=0
for attempt in $(seq 1 20); do
  if [[ -f "$PID_FILE" ]] && ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Django process exited (PID $(cat "$PID_FILE"))."
    _show_log_tail
    exit 1
  fi

  for path in "${PATHS[@]}"; do
    code="$(_http_code "${BASE}${path}")"
    if [[ "$code" != "000" ]]; then
      UP=1
      echo "  HTTP ${code}  ${path}"
      if [[ "$code" =~ ^2 ]]; then
        DATA_OK=1
      fi
    fi
  done

  if [[ "$UP" -eq 1 ]]; then
    break
  fi
  sleep 1
done

if [[ "$UP" -eq 0 ]]; then
  echo ""
  echo "Django did not respond on port ${PORT}."
  _show_log_tail
  echo ""
  echo "Common fixes:"
  echo "  cd $MANAGE_DIR && $PY -m pip install -r requirements.txt"
  echo "  cd $MANAGE_DIR && $PY manage.py migrate"
  echo "  cd $MANAGE_DIR && $PY manage.py runserver 127.0.0.1:${PORT}"
  exit 1
fi

_set_engine_env "OPENTRADER_USE_OLD_UI" "1"
_set_engine_env "MT5_AUTO_SYNC" "0"

if [[ "$DATA_OK" -eq 1 ]]; then
  _set_engine_env "OPENTRADER_BACKEND_URL" "http://127.0.0.1:${PORT}"
  _set_engine_env "OPENTRADER_DJANGO_PROXY" "1"
  echo "==> Django has live data — enabled OPENTRADER_DJANGO_PROXY=1"
else
  sed -i '/^OPENTRADER_BACKEND_URL=/d' "$ENGINE_DIR/.env" 2>/dev/null || true
  _set_engine_env "OPENTRADER_DJANGO_PROXY" "0"
  echo "==> Django up but no MT5 data yet — proxy disabled, chart uses local fallback"
fi

echo ""
echo "==> Django is up on ${BASE}"
if [[ "$DATA_OK" -eq 0 ]]; then
  echo "==> Warning: no 2xx API responses yet (MT5 data may still be missing)."
  echo "    Chart engine will use yahoo/synthetic fallback for /api/history/."
  echo "    For live BlackBull data: log into MT5 on Windows and run the bridge."
fi
echo "==> Configured $ENGINE_DIR/.env with OPENTRADER_BACKEND_URL"
echo ""
echo "Restart chart engine:"
echo "  cd $ENGINE_DIR"
echo "  bash scripts/stop_opentrader.sh"
echo "  FORCE=1 bash run.sh"
echo ""
echo "Test:"
echo "  curl -s '${BASE}/api/history/?symbol=XRPUSD&interval=1m&range=1d&source=blackbull' | head -c 200"
echo "  curl -s 'http://127.0.0.1:8010/api/history/?symbol=XRPUSD&interval=1m&range=1d&source=blackbull' | head -c 200"
