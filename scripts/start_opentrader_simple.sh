#!/usr/bin/env bash
# Minimal OpenTrader start — no patches, just Django on :8010.
#
# Usage:
#   bash scripts/start_opentrader_simple.sh
#   bash scripts/start_opentrader_simple.sh /home/heinz/OpenTrader
#
set -euo pipefail

CHART_ROOT="${1:-/home/heinz/OpenTrader}"
PORT="${PORT:-8010}"

if [[ ! -f "$CHART_ROOT/manage.py" ]]; then
  echo "ERROR: $CHART_ROOT/manage.py not found"
  exit 1
fi

cd "$CHART_ROOT"

PYTHON=""
if [[ -x "$CHART_ROOT/.venv/bin/python3" ]]; then
  PYTHON="$CHART_ROOT/.venv/bin/python3"
elif [[ -x "$CHART_ROOT/.venv/bin/python" ]]; then
  PYTHON="$CHART_ROOT/.venv/bin/python"
else
  echo "ERROR: No venv at $CHART_ROOT/.venv"
  echo "  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

PIP=""
if [[ -x "$CHART_ROOT/.venv/bin/pip3" ]]; then
  PIP="$CHART_ROOT/.venv/bin/pip3"
elif [[ -x "$CHART_ROOT/.venv/bin/pip" ]]; then
  PIP="$CHART_ROOT/.venv/bin/pip"
fi

if ! "$PYTHON" -c "import django" 2>/dev/null; then
  echo "==> Installing Django into venv ..."
  if [[ -n "$PIP" ]]; then
    "$PIP" install -r requirements.txt 2>/dev/null || \
      "$PIP" install django djangorestframework django-cors-headers yfinance pandas requests
  else
    "$PYTHON" -m pip install django djangorestframework django-cors-headers yfinance pandas requests
  fi
fi

if ! "$PYTHON" -c "import django" 2>/dev/null; then
  echo "ERROR: Django not in venv. Run:"
  echo "  cd $CHART_ROOT && source .venv/bin/activate && pip3 install -r requirements.txt"
  exit 1
fi

echo "==> Django $("$PYTHON" -c 'import django; print(django.get_version())')"
echo "==> Checking project ..."
if ! "$PYTHON" manage.py check 2>&1; then
  echo ""
  echo "ERROR: manage.py check failed — fix Django settings above, then retry."
  exit 1
fi

pkill -f "manage.py runserver.*${PORT}" 2>/dev/null || true
fuser -k "${PORT}/tcp" 2>/dev/null || true
sleep 1

echo ""
echo "==> Starting http://127.0.0.1:${PORT}"
echo "    Ctrl+C to stop"
exec "$PYTHON" manage.py runserver "127.0.0.1:${PORT}"
