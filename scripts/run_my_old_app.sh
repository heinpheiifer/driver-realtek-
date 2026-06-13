#!/usr/bin/env bash
# Run YOUR original OpenTrader — NOT the new git engine in opentrade-app.
#
# Your old working app:
#   Chart + API:  ~/OpenTrader  (Django + MT5 bridge)
#   Git engine:   ~/opentrade-app / ~/opentrader-app  (new — do not use for live BlackBull)
#
# Usage:
#   bash ~/opentrader-app/scripts/run_my_old_app.sh
#
set -euo pipefail

ENGINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART_ROOT="${1:-/home/heinz/OpenTrader}"
ENGINE_DIR="${2:-/home/heinz/opentrade-app}"
CHART_PORT="${CHART_PORT:-8010}"
DJANGO_PORT="${DJANGO_PORT:-8000}"

echo "=============================================="
echo " YOUR ORIGINAL OpenTrader (BlackBull + MT5)"
echo "=============================================="
echo ""
echo "  Old app (yours):     $CHART_ROOT"
echo "  New git engine:      $ENGINE_DIR  ← NOT what you want for live data"
echo ""

_python() {
  command -v python3 >/dev/null && echo python3 || echo python
}

_stop_port() {
  local port="$1"
  if command -v fuser >/dev/null; then
    fuser -k "${port}/tcp" 2>/dev/null || true
  fi
  pkill -f "uvicorn opentrader.main" 2>/dev/null || true
  pkill -f "manage.py runserver.*:${port}" 2>/dev/null || true
  sleep 1
}

_find_manage() {
  for dir in "$CHART_ROOT" "$CHART_ROOT/backend" "$CHART_ROOT/server" "$CHART_ROOT/api"; do
    [[ -f "$dir/manage.py" ]] && echo "$dir" && return 0
  done
  find "$CHART_ROOT" -maxdepth 5 -name manage.py -print -quit 2>/dev/null || true
}

_find_run_script() {
  for f in "$CHART_ROOT/run.sh" "$CHART_ROOT/start.sh" "$CHART_ROOT/scripts/run.sh"; do
    [[ -x "$f" ]] && echo "$f" && return 0
  done
  return 1
}

echo "==> Stopping new git engine on ports ${CHART_PORT} and ${DJANGO_PORT} ..."
_stop_port "$CHART_PORT"
_stop_port "$DJANGO_PORT"

MANAGE_DIR="$(_find_manage || true)"
RUN_SCRIPT="$(_find_run_script || true)"

# --- Mode A: OpenTrader has its own run script (your original entry point) ---
if [[ -n "$RUN_SCRIPT" ]]; then
  echo ""
  echo "==> Found YOUR original launcher: $RUN_SCRIPT"
  echo "    Starting on http://127.0.0.1:${CHART_PORT}"
  echo ""
  cd "$CHART_ROOT"
  export PORT="$CHART_PORT"
  exec bash "$RUN_SCRIPT"
fi

# --- Mode B: Django project (manage.py) — this IS your old app backend ---
if [[ -n "$MANAGE_DIR" && -f "$MANAGE_DIR/manage.py" ]]; then
  PY="$(_python)"
  echo ""
  echo "==> Found YOUR Django app: $MANAGE_DIR"
  echo "    This is your original OpenTrader with BlackBull/MT5 API."
  echo ""
  cd "$MANAGE_DIR"

  for venv in .venv venv "$ENGINE_DIR/.venv"; do
    if [[ -f "$venv/bin/activate" ]]; then
      # shellcheck disable=SC1091
      source "$venv/bin/activate"
      break
    fi
  done

  if [[ -f requirements.txt ]]; then
    "$PY" -m pip install -q -r requirements.txt 2>/dev/null || true
  fi
  "$PY" manage.py migrate --noinput 2>/dev/null || true

  LOG="$CHART_ROOT/.opentrader_django.log"
  echo "==> Starting Django on http://127.0.0.1:${CHART_PORT}"
  echo "    Log: $LOG"
  echo ""
  echo "    MT5 bridge (Windows, BlackBull MT5 open):"
  echo "      set OPENTRADER_URL=http://127.0.0.1:${CHART_PORT}"
  echo "      python scripts\\mt5_python_bridge.py --all-symbols --interval 60"
  echo ""
  echo "    Open chart: http://127.0.0.1:${CHART_PORT}"
  echo "=============================================="
  exec "$PY" manage.py runserver "127.0.0.1:${CHART_PORT}"
fi

# --- Mode C: No Django — chart UI only; use Django stack + MT5 bridge ---
echo ""
echo "==> No manage.py in $CHART_ROOT"
echo "    Searching for your app..."
bash "$ENGINE_ROOT/scripts/recover_old_chart.sh" "$HOME" || true

echo ""
echo "==> Starting fallback stack: Django (if found) + chart + MT5 bridge API"
echo ""

ENV_FILE="$ENGINE_DIR/.env"
mkdir -p "$ENGINE_DIR"
touch "$ENV_FILE"

_set_env() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
  else
    echo "${key}=${val}" >> "$ENV_FILE"
  fi
}

_set_env "OPENTRADER_USE_OLD_UI" "1"
_set_env "OPENTRADER_OLD_APP" "$CHART_ROOT"
_set_env "OPENTRADER_DJANGO_PROXY" "1"
_set_env "MT5_AUTO_SYNC" "0"
_set_env "MT5_WINE_SYNC" "1"

if [[ -f "$CHART_ROOT/frontend/dist/index.html" ]]; then
  _set_env "OPENTRADER_UI_INDEX" "$CHART_ROOT/frontend/dist/index.html"
fi

bash "$ENGINE_ROOT/scripts/start_opentrader_django.sh" "$CHART_ROOT" "$ENGINE_DIR" || true
_set_env "OPENTRADER_BACKEND_URL" "http://127.0.0.1:${DJANGO_PORT}"

echo ""
echo "==> MT5 bridge must push live BlackBull data:"
echo "    Linux (Wine MT5):  bash $ENGINE_ROOT/scripts/setup_live_blackbull.sh $ENGINE_DIR"
echo "    Windows MT5:       set OPENTRADER_URL=http://127.0.0.1:${CHART_PORT}"
echo "                       python scripts\\mt5_python_bridge.py --all-symbols --interval 60"
echo ""

cd "$ENGINE_DIR"
export OPENTRADER_USE_OLD_UI=1
export OPENTRADER_OLD_APP="$CHART_ROOT"
export OPENTRADER_DJANGO_PROXY=1
export PORT="$CHART_PORT"
FORCE=1 bash run.sh
