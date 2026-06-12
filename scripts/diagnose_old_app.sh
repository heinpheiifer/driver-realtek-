#!/usr/bin/env bash
# Diagnose why the old Open Trader chart UI is not showing.
set -euo pipefail

OLD_APP="${1:-${OPENTRADER_OLD_APP:-/home/heinz/opentrade-app}}"
PORT="${PORT:-8010}"

echo "=== Open Trader old app diagnostic ==="
echo "Path: $OLD_APP"
echo ""

if [[ ! -d "$OLD_APP" ]]; then
  echo "ERROR: Folder does not exist: $OLD_APP"
  exit 1
fi

echo "--- HTML files ---"
find "$OLD_APP" -maxdepth 4 -name '*.html' 2>/dev/null | head -20 || echo "(none)"

echo ""
echo "--- UI backup ---"
if [[ -d "$OLD_APP/.opentrader_ui_backup" ]]; then
  ls -la "$OLD_APP/.opentrader_ui_backup/" || true
  if [[ -L "$OLD_APP/.opentrader_ui_backup/latest" ]]; then
    echo "latest → $(readlink "$OLD_APP/.opentrader_ui_backup/latest")"
  fi
else
  echo "No backup folder (.opentrader_ui_backup)"
fi

echo ""
echo "--- .env ---"
if [[ -f "$OLD_APP/.env" ]]; then
  grep -E '^(OPENTRADER_|MT5_|PORT=)' "$OLD_APP/.env" 2>/dev/null || true
else
  echo "No .env file"
fi

echo ""
echo "--- BlackBull cache ---"
ls -la "$OLD_APP/trading_data/"*blackbull* 2>/dev/null | head -10 || echo "(no blackbull CSV cache)"
ls -la "$OLD_APP/trading_data/blackbull_import/" 2>/dev/null | head -10 || echo "(no blackbull_import)"

echo ""
echo "--- Server health (if running) ---"
if curl -sf "http://127.0.0.1:${PORT}/api/health" 2>/dev/null | python3 -m json.tool 2>/dev/null; then
  :
else
  echo "Server not responding on port $PORT"
fi

echo ""
echo "--- Fix commands ---"
echo "  bash scripts/restore_old_ui.sh $OLD_APP"
echo "  FORCE=1 bash run.sh"
echo "  # or from git repo:"
echo "  FORCE=1 bash scripts/setup_old_app.sh $OLD_APP"
