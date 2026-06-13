#!/usr/bin/env bash
# Diagnose ~/OpenTrader — blank chart, Firefox, API, patches.
#
# Usage:
#   bash scripts/diagnose_opentrader.sh
#   bash scripts/diagnose_opentrader.sh /home/heinz/OpenTrader
#
set -euo pipefail

CHART_ROOT="${1:-/home/heinz/OpenTrader}"
PORT="${PORT:-8010}"

echo "=============================================="
echo " OpenTrader diagnostic"
echo "=============================================="
echo "Path: $CHART_ROOT"
echo "Port: $PORT"
echo ""

if [[ ! -d "$CHART_ROOT" ]]; then
  echo "ERROR: $CHART_ROOT not found"
  exit 1
fi

echo "--- manage.py ---"
find "$CHART_ROOT" -maxdepth 4 -name manage.py -not -path '*/.venv/*' 2>/dev/null | head -3 || echo "(none)"

echo ""
echo "--- Chart HTML ---"
for f in \
  "$CHART_ROOT/frontend/dist/index.html" \
  "$CHART_ROOT/frontend/index.html" \
  "$CHART_ROOT/staticfiles/index.html"; do
  if [[ -f "$f" ]]; then
    echo "  $f"
    grep -E 'bookmap_below|ot-bookmap|chart_patch' "$f" 2>/dev/null | head -3 | sed 's/^/    /' || echo "    (no bookmap patch)"
  fi
done

echo ""
echo "--- Django venv ---"
if [[ -x "$CHART_ROOT/.venv/bin/python3" ]]; then
  "$CHART_ROOT/.venv/bin/python3" -c "import django; print('  Django', django.get_version())" 2>/dev/null || echo "  Django NOT importable in .venv"
elif [[ -x "$CHART_ROOT/.venv/bin/python" ]]; then
  "$CHART_ROOT/.venv/bin/python" -c "import django; print('  Django', django.get_version())" 2>/dev/null || echo "  Django NOT importable in .venv"
else
  echo "  No .venv/bin/python3"
fi

echo ""
echo "--- Server (127.0.0.1 vs localhost) ---"
_check() {
  local url="$1"
  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 2 "$url" 2>/dev/null || echo "000")"
  echo "  $url → HTTP $code"
}

_check "http://127.0.0.1:${PORT}/"
_check "http://localhost:${PORT}/"
_check "http://127.0.0.1:${PORT}/chart_patch/bookmap_below_chart.css"
_check "http://127.0.0.1:${PORT}/api/history/?symbol=BTCUSD&interval=5m&range=1d&source=blackbull"

echo ""
echo "--- API history sample ---"
HIST="$(curl -sf --connect-timeout 3 \
  "http://127.0.0.1:${PORT}/api/history/?symbol=BTCUSD&interval=5m&range=1d&source=blackbull" 2>/dev/null | head -c 500 || true)"
if [[ -n "$HIST" ]]; then
  echo "$HIST" | python3 -m json.tool 2>/dev/null | head -20 || echo "$HIST"
else
  echo "  (no response — is Django running? bash scripts/run_my_old_app.sh)"
fi

echo ""
echo "--- Process on :${PORT} ---"
if command -v ss >/dev/null; then
  ss -tlnp 2>/dev/null | grep ":${PORT} " || echo "  nothing listening on ${PORT}"
elif command -v fuser >/dev/null; then
  fuser "${PORT}/tcp" 2>/dev/null || echo "  nothing on ${PORT}"
fi

echo ""
echo "--- Fix commands ---"
echo "  # 1. Remove layout patches (if chart blank / Firefox freeze):"
echo "  bash scripts/unpatch_bookmap.sh $CHART_ROOT"
echo ""
echo "  # 2. Start app:"
echo "  bash scripts/run_my_old_app.sh"
echo ""
echo "  # 3. Open in Firefox:"
echo "  http://127.0.0.1:${PORT}"
echo ""
echo "  # 4. Bookmap-below (only after chart works):"
echo "  OPENTRADER_BOOKMAP_BELOW=1 bash scripts/run_my_old_app.sh"
