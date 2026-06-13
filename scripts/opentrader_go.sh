#!/usr/bin/env bash
# ONE command to start ~/OpenTrader — tries uv, venv, then system pip.
#
# Usage:
#   bash scripts/opentrader_go.sh
#   bash scripts/opentrader_go.sh /home/heinz/OpenTrader
#
set -uo pipefail

ENGINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART_ROOT="${1:-/home/heinz/OpenTrader}"
PORT="${PORT:-8010}"
LOG="$CHART_ROOT/.opentrader_start.log"
PY=""

exec > >(tee -a "$LOG") 2>&1

echo "=============================================="
echo " OpenTrader GO — $(date -Iseconds)"
echo "=============================================="
echo "App:  $CHART_ROOT"
echo "Log:  $LOG"
echo ""

if [[ ! -f "$CHART_ROOT/manage.py" ]]; then
  echo "ERROR: $CHART_ROOT/manage.py not found"
  exit 1
fi

cd "$CHART_ROOT"

# Remove layout patches that freeze Firefox
bash "$ENGINE_ROOT/scripts/unpatch_bookmap.sh" "$CHART_ROOT" 2>/dev/null || true

_stop_ports() {
  pkill -f "manage.py runserver" 2>/dev/null || true
  pkill -f "uvicorn opentrader.main" 2>/dev/null || true
  fuser -k "${PORT}/tcp" 2>/dev/null || true
  fuser -k 8011/tcp 2>/dev/null || true
  sleep 1
}

_find_py() {
  local c
  for c in \
    "$CHART_ROOT/.venv/bin/python3" \
    "$CHART_ROOT/.venv/bin/python" \
    "$(command -v python3 2>/dev/null)"; do
    [[ -n "$c" && -x "$c" ]] || continue
    if "$c" -c "import django" 2>/dev/null; then
      PY="$c"
      return 0
    fi
  done
  return 1
}

_try_uv() {
  echo "==> Try: uv (fast reliable venv)"
  if ! command -v uv >/dev/null 2>&1; then
    if [[ -x "$HOME/.local/bin/uv" ]]; then
      export PATH="$HOME/.local/bin:$PATH"
    else
      echo "    installing uv to ~/.local/bin ..."
      curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$HOME/.local/bin" sh 2>/dev/null || return 1
      export PATH="$HOME/.local/bin:$PATH"
    fi
  fi
  command -v uv >/dev/null || return 1

  rm -rf .venv
  uv venv .venv || return 1
  uv pip install -r requirements.txt || uv pip install django djangorestframework django-cors-headers yfinance pandas requests python-dotenv
  PY="$CHART_ROOT/.venv/bin/python"
  [[ -x "$PY" ]] || PY="$CHART_ROOT/.venv/bin/python3"
  [[ -x "$PY" ]] || return 1
  "$PY" -c "import django" 2>/dev/null
}

_try_venv() {
  echo "==> Try: python3 -m venv"
  if ! python3 -c "import venv" 2>/dev/null; then
    echo "    SKIP — install: sudo apt install python3-venv python3-pip"
    return 1
  fi
  rm -rf .venv
  python3 -m venv .venv || return 1
  for candidate in .venv/bin/python3 .venv/bin/python; do
    [[ -x "$candidate" ]] || continue
    PY="$CHART_ROOT/$candidate"
    break
  done
  [[ -n "$PY" ]] || return 1
  "$PY" -m ensurepip --upgrade 2>/dev/null || true
  "$PY" -m pip install --upgrade pip
  "$PY" -m pip install -r requirements.txt
  "$PY" -c "import django" 2>/dev/null
}

_try_system_pip() {
  echo "==> Try: system python3 + pip (no venv)"
  PY="$(command -v python3)"
  if python3 -m pip install --break-system-packages -r requirements.txt 2>/dev/null; then
    :
  elif python3 -m pip install --user -r requirements.txt; then
    :
  else
    return 1
  fi
  "$PY" -c "import django" 2>/dev/null
}

_start() {
  _stop_ports
  echo ""
  echo "==> Python: $PY"
  echo "==> Django: $("$PY" -c 'import django; print(django.get_version())')"
  echo "==> migrate ..."
  "$PY" manage.py migrate --noinput 2>/dev/null || "$PY" manage.py migrate || true
  echo "==> check ..."
  if ! "$PY" manage.py check 2>&1; then
    echo ""
    echo "ERROR: manage.py check failed."
    echo "If settings.py was patched, restore:"
    echo "  cd $CHART_ROOT && git checkout -- opentrader/settings.py"
    exit 1
  fi
  echo ""
  echo "=============================================="
  echo " RUNNING — open http://127.0.0.1:${PORT}"
  echo " Ctrl+C to stop"
  echo "=============================================="
  exec "$PY" manage.py runserver "127.0.0.1:${PORT}"
}

# --- pick install method ---
if _find_py; then
  echo "==> Existing Python already has Django: $PY"
  _start
fi

if _try_uv; then
  echo "    OK (uv)"
  _start
fi

if _try_venv; then
  echo "    OK (venv)"
  _start
fi

if _try_system_pip; then
  echo "    OK (system pip)"
  _start
fi

echo ""
echo "=============================================="
echo " FAILED — could not install Django"
echo "=============================================="
echo ""
echo "Run these commands and paste ALL output:"
echo ""
echo "  python3 --version"
echo "  python3 -m pip --version"
echo "  sudo apt install python3-venv python3-pip"
echo "  bash $ENGINE_ROOT/scripts/opentrader_go.sh $CHART_ROOT"
echo ""
echo "Full log: $LOG"
exit 1
