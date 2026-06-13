#!/usr/bin/env bash
# Rebuild ~/OpenTrader venv when pip says Django OK but python cannot import it.
#
# Usage:
#   bash scripts/fix_opentrader_venv.sh
#   bash scripts/fix_opentrader_venv.sh /home/heinz/OpenTrader
#
set -euo pipefail

CHART_ROOT="${1:-/home/heinz/OpenTrader}"
PORT="${PORT:-8010}"

if [[ ! -f "$CHART_ROOT/manage.py" ]]; then
  echo "ERROR: $CHART_ROOT/manage.py not found"
  exit 1
fi

cd "$CHART_ROOT"

if ! command -v python3 >/dev/null; then
  echo "ERROR: python3 not found"
  exit 1
fi

SYS_PY="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "==> System python3: $(command -v python3) (Python $SYS_PY)"

if [[ -d .venv ]]; then
  echo "==> Removing broken .venv ..."
  rm -rf .venv
fi

echo "==> Creating fresh venv with python3 ..."
python3 -m venv .venv

PY="$CHART_ROOT/.venv/bin/python3"
if [[ ! -x "$PY" ]]; then
  PY="$CHART_ROOT/.venv/bin/python"
fi

echo "==> Venv python: $PY ($("$PY" -c 'import sys; print(sys.version)'))"

echo "==> Installing packages (python -m pip) ..."
"$PY" -m pip install --upgrade pip
if [[ -f requirements.txt ]]; then
  "$PY" -m pip install -r requirements.txt
else
  "$PY" -m pip install django djangorestframework django-cors-headers yfinance pandas requests python-dotenv
fi

echo "==> Verify Django import ..."
if ! "$PY" -c "import django; print('Django', django.get_version())"; then
  echo "ERROR: Django still not importable after venv rebuild."
  "$PY" -m pip list | head -20
  exit 1
fi

echo "==> migrate ..."
"$PY" manage.py migrate --noinput 2>/dev/null || "$PY" manage.py migrate || true

echo "==> django check ..."
"$PY" manage.py check

pkill -f "manage.py runserver.*${PORT}" 2>/dev/null || true
fuser -k "${PORT}/tcp" 2>/dev/null || true
sleep 1

echo ""
echo "=============================================="
echo " OK — starting OpenTrader"
echo " http://127.0.0.1:${PORT}"
echo "=============================================="
echo ""
exec "$PY" manage.py runserver "127.0.0.1:${PORT}"
