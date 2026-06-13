#!/usr/bin/env bash
# Minimal OpenTrader start — no patches, just Django on :8010.
#
# Usage:
#   bash scripts/start_opentrader_simple.sh
#   bash scripts/start_opentrader_simple.sh /home/heinz/OpenTrader
#
set -euo pipefail

ENGINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART_ROOT="${1:-/home/heinz/OpenTrader}"
PORT="${PORT:-8010}"

if [[ ! -f "$CHART_ROOT/manage.py" ]]; then
  echo "ERROR: $CHART_ROOT/manage.py not found"
  exit 1
fi

cd "$CHART_ROOT"

PY=""
for candidate in "$CHART_ROOT/.venv/bin/python3" "$CHART_ROOT/.venv/bin/python"; do
  if [[ -x "$candidate" ]]; then
    PY="$candidate"
    break
  fi
done

_ensure_django() {
  if [[ -n "$PY" ]] && "$PY" -c "import django" 2>/dev/null; then
    return 0
  fi
  echo "==> Django not importable — rebuilding venv ..."
  exec bash "$ENGINE_ROOT/scripts/fix_opentrader_venv.sh" "$CHART_ROOT"
}

if [[ -z "$PY" ]] || [[ ! -d "$CHART_ROOT/.venv" ]]; then
  echo "==> No usable venv — creating ..."
  exec bash "$ENGINE_ROOT/scripts/fix_opentrader_venv.sh" "$CHART_ROOT"
fi

_ensure_django

echo "==> Django $("$PY" -c 'import django; print(django.get_version())')"
echo "==> Python: $PY"

echo "==> Checking project ..."
if ! "$PY" manage.py check 2>&1; then
  echo ""
  echo "ERROR: manage.py check failed."
  echo "Try: bash scripts/fix_opentrader_venv.sh $CHART_ROOT"
  exit 1
fi

pkill -f "manage.py runserver.*${PORT}" 2>/dev/null || true
fuser -k "${PORT}/tcp" 2>/dev/null || true
sleep 1

echo ""
echo "==> Starting http://127.0.0.1:${PORT}"
echo "    Ctrl+C to stop"
exec "$PY" manage.py runserver "127.0.0.1:${PORT}"
