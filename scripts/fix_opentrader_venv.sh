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
  echo "ERROR: python3 not found. Run: sudo apt install python3 python3-pip python3-venv"
  exit 1
fi

SYS_PY="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "==> System python3: $(command -v python3) (Python $SYS_PY)"

if ! python3 -c "import venv" 2>/dev/null; then
  echo ""
  echo "ERROR: python3-venv is not installed."
  echo "Run:"
  echo "  sudo apt update"
  echo "  sudo apt install python3-venv python3-pip python${SYS_PY}-venv"
  echo "Then re-run this script."
  exit 1
fi

if [[ -d .venv ]]; then
  echo "==> Removing old .venv ..."
  rm -rf .venv
fi

echo "==> Creating fresh .venv ..."
if ! python3 -m venv .venv; then
  echo ""
  echo "ERROR: python3 -m venv failed."
  echo "Run: sudo apt install python3-venv python${SYS_PY}-venv"
  exit 1
fi

PY=""
for candidate in .venv/bin/python3 .venv/bin/python; do
  if [[ -x "$candidate" ]]; then
    PY="$CHART_ROOT/$candidate"
    break
  fi
done

if [[ -z "$PY" ]]; then
  echo ""
  echo "ERROR: .venv was created but has no python in .venv/bin/"
  echo "Contents of .venv/bin:"
  ls -la .venv/bin/ 2>/dev/null || echo "  (missing .venv/bin — venv package broken)"
  echo ""
  echo "Fix:"
  echo "  sudo apt install python3-venv python${SYS_PY}-venv"
  echo "  rm -rf .venv && python3 -m venv .venv"
  exit 1
fi

echo "==> Venv python: $PY"
"$PY" -c 'import sys; print("    version:", sys.version)'

echo "==> Installing pip + requirements ..."
if ! "$PY" -m pip --version >/dev/null 2>&1; then
  echo "==> bootstrapping pip ..."
  "$PY" -m ensurepip --upgrade 2>/dev/null || true
fi
"$PY" -m pip install --upgrade pip
if [[ -f requirements.txt ]]; then
  "$PY" -m pip install -r requirements.txt
else
  "$PY" -m pip install django djangorestframework django-cors-headers yfinance pandas requests python-dotenv
fi

echo "==> Verify Django ..."
if ! "$PY" -c "import django; print('Django', django.get_version())"; then
  echo "ERROR: Django not importable."
  "$PY" -m pip list | head -25
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
