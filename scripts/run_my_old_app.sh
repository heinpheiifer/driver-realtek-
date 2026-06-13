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
GIT_ENGINE="${3:-/home/heinz/opentrader-app}"
CHART_PORT="${CHART_PORT:-8010}"
DJANGO_PORT="${DJANGO_PORT:-8000}"

echo "=============================================="
echo " YOUR ORIGINAL OpenTrader (BlackBull + MT5)"
echo "=============================================="
echo ""
echo "  Old app (yours):     $CHART_ROOT"
echo "  Engine folder:       $ENGINE_DIR"
echo ""

_stop_port() {
  local port="$1"
  if command -v fuser >/dev/null; then
    fuser -k "${port}/tcp" 2>/dev/null || true
  fi
  pkill -f "uvicorn opentrader.main" 2>/dev/null || true
  pkill -f "manage.py runserver" 2>/dev/null || true
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

_activate_python_env() {
  local manage_dir="$1"
  local candidates=(
    "$manage_dir/.venv"
    "$manage_dir/venv"
    "$CHART_ROOT/.venv"
    "$CHART_ROOT/venv"
    "$ENGINE_DIR/.venv"
    "$GIT_ENGINE/.venv"
    "$HOME/opentrade-app/.venv"
    "$HOME/opentrader-app/.venv"
  )
  for venv in "${candidates[@]}"; do
    if [[ -f "$venv/bin/activate" ]]; then
      # shellcheck disable=SC1091
      source "$venv/bin/activate"
      echo "==> Python venv: $venv"
      return 0
    fi
  done

  echo "==> No venv found — creating $manage_dir/.venv"
  if ! python3 -c "import venv" 2>/dev/null; then
    echo "ERROR: python3-venv missing. Run: sudo apt install python3-venv python3-pip"
    exit 1
  fi
  python3 -m venv "$manage_dir/.venv"
  # shellcheck disable=SC1091
  source "$manage_dir/.venv/bin/activate"
  pip install -q --upgrade pip
  echo "==> Created venv: $manage_dir/.venv"
}

_install_django_deps() {
  local manage_dir="$1"
  local installed=0

  for req in \
    "$manage_dir/requirements.txt" \
    "$CHART_ROOT/requirements.txt" \
    "$ENGINE_DIR/requirements.txt" \
    "$GIT_ENGINE/requirements.txt"; do
    if [[ -f "$req" ]]; then
      echo "==> Installing from $req"
      pip install -r "$req"
      installed=1
      break
    fi
  done

  if ! python -c "import django" 2>/dev/null; then
    echo "==> Installing Django (minimum for OpenTrader)..."
    pip install "django>=4.2" djangorestframework django-cors-headers python-dotenv requests
    installed=1
  fi

  if ! python -c "import django" 2>/dev/null; then
    echo "ERROR: Django still not installed after pip install."
    echo "Try manually:"
    echo "  cd $manage_dir && python3 -m venv .venv && source .venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
  fi

  if [[ "$installed" -eq 1 ]]; then
    echo "==> Django OK: $(python -c 'import django; print(django.get_version())')"
  fi
}

echo "==> Stopping anything on ports ${CHART_PORT} and ${DJANGO_PORT} ..."
_stop_port "$CHART_PORT"
_stop_port "$DJANGO_PORT"

MANAGE_DIR="$(_find_manage || true)"
RUN_SCRIPT="$(_find_run_script || true)"

# --- Mode A: OpenTrader has its own run script ---
if [[ -n "$RUN_SCRIPT" ]]; then
  echo ""
  echo "==> Found YOUR original launcher: $RUN_SCRIPT"
  cd "$CHART_ROOT"
  export PORT="$CHART_PORT"
  exec bash "$RUN_SCRIPT"
fi

# --- Mode B: Django project (manage.py) ---
if [[ -n "$MANAGE_DIR" && -f "$MANAGE_DIR/manage.py" ]]; then
  echo ""
  echo "==> Found YOUR Django app: $MANAGE_DIR"
  cd "$MANAGE_DIR"

  _activate_python_env "$MANAGE_DIR"
  _install_django_deps "$MANAGE_DIR"

  echo "==> Running migrations..."
  python manage.py migrate --noinput 2>/dev/null || python manage.py migrate || true

  LOG="$CHART_ROOT/.opentrader_django.log"
  echo ""
  echo "==> Starting YOUR OpenTrader on http://127.0.0.1:${CHART_PORT}"
  echo "    Log: $LOG"
  echo ""
  echo "    MT5 bridge (Windows, BlackBull MT5 open):"
  echo "      set OPENTRADER_URL=http://127.0.0.1:${CHART_PORT}"
  echo "      python scripts\\mt5_python_bridge.py --all-symbols --interval 60"
  echo ""
  echo "    Open chart: http://127.0.0.1:${CHART_PORT}"
  echo "=============================================="
  exec python manage.py runserver "127.0.0.1:${CHART_PORT}"
fi

# --- Mode C: fallback stack ---
echo ""
echo "==> No manage.py in $CHART_ROOT"
bash "$ENGINE_ROOT/scripts/recover_old_chart.sh" "$HOME" || true

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

cd "$ENGINE_DIR"
export OPENTRADER_USE_OLD_UI=1
export OPENTRADER_OLD_APP="$CHART_ROOT"
export OPENTRADER_DJANGO_PROXY=1
export PORT="$CHART_PORT"
FORCE=1 bash run.sh
