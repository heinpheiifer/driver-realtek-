#!/usr/bin/env bash
# BlackBull MT5 setup checker — run on Linux where Open Trader lives
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== Open Trader · BlackBull MT5 Setup ==="
echo ""

# Check if bridge API is running
API_PORT="${OPENTRADER_URL:-http://127.0.0.1:8011}"
API_PORT="${API_PORT#http://}"
API_PORT="${API_PORT#https://}"
API_PORT="${API_PORT%%/*}"
HOST="${API_PORT%%:*}"
PORT="${API_PORT##*:}"

if curl -sf "http://${HOST}:${PORT}/api/health" >/dev/null 2>&1; then
  echo "✓ Open Trader API running on http://${HOST}:${PORT}"
else
  echo "✗ Open Trader API not reachable on http://${HOST}:${PORT}"
  echo "  Run: bash install_and_run.sh"
  echo ""
fi

# Check for imported data
IMPORT_DIR="$ROOT/trading_data/blackbull_import"
SYMBOL_MANIFEST="$ROOT/trading_data/blackbull_symbols.json"
IMPORT_COUNT=0
if [[ -d "$IMPORT_DIR" ]]; then
  IMPORT_COUNT=$(find "$IMPORT_DIR" -name "*.csv" 2>/dev/null | wc -l)
fi

if [[ "$IMPORT_COUNT" -gt 0 ]]; then
  echo "✓ Found $IMPORT_COUNT CSV file(s) in trading_data/blackbull_import/"
  ls -1 "$IMPORT_DIR"/*.csv 2>/dev/null | head -5
else
  echo "✗ No BlackBull CSV data yet in trading_data/blackbull_import/"
fi

if [[ -f "$SYMBOL_MANIFEST" ]]; then
  COUNT=$(python3 -c "import json; print(json.load(open('$SYMBOL_MANIFEST'))['count'])" 2>/dev/null || echo "?")
  echo "✓ Symbol manifest: $COUNT symbols ($(basename "$SYMBOL_MANIFEST"))"
else
  echo "✗ No symbol manifest (trading_data/blackbull_symbols.json)"
fi

echo ""
echo "=== MT5 on Linux? ==="
if python3 -c "import MetaTrader5" 2>/dev/null; then
  echo "✓ MetaTrader5 package installed (Windows/Wine only works with MT5 terminal)"
else
  echo "○ MetaTrader5 not available on Linux — this is normal."
fi

echo ""
echo "=== HOW TO FIX (your setup: Linux Open Trader + Windows BlackBull MT5) ==="
echo ""
echo "STEP 1 — On Linux (this machine), start the bridge API:"
echo "  cd ~/opentrader-app"
echo "  bash install_and_run.sh          # uses :8011 if old chart on :8010"
echo ""
echo "STEP 2 — On Windows (BlackBull MT5 PC), clone repo and run bridge:"
echo "  git clone https://github.com/heinpheiifer/driver-realtek-.git opentrader-app"
echo "  cd opentrader-app"
echo "  python -m venv .venv"
echo "  .venv\\Scripts\\pip install -r requirements.txt -r requirements-mt5.txt"
echo ""
echo "  Create .env (copy from .env.blackbull.example) with YOUR credentials:"
echo "    MT5_LOGIN=your_account_number"
echo "    MT5_PASSWORD=your_password"
echo "    MT5_SERVER=BlackBullMarkets-Live"
echo "    MT5_PATH=C:\\Program Files\\BlackBull Markets MT5\\terminal64.exe"
echo "    OPENTRADER_URL=http://LINUX-IP:8011"
echo ""
echo "  Make sure BlackBull MT5 is OPEN and logged in, then:"
echo "  .venv\\Scripts\\python scripts\\mt5_python_bridge.py --all-symbols --interval 60"
echo ""
echo "STEP 3 — In Open Trader chart, select BlackBull → Load"
echo ""
echo "=== ALTERNATIVE: Manual CSV import (no Windows bridge) ==="
echo "  1. In MT5: run scripts/BlackBullExportToOpenTrader.mq5 on your chart"
echo "  2. Copy CSV from MQL5/Files/blackbull_import/ to Linux:"
echo "     bash scripts/import_blackbull_csv.sh /path/to/xrpusd_m1.csv XRPUSD M1"
echo ""

# Show Linux IP for Windows to connect
if command -v hostname >/dev/null; then
  echo "Your Linux IP (use in OPENTRADER_URL on Windows):"
  hostname -I 2>/dev/null | awk '{print "  http://" $1 ":8011"}' || ip -4 addr show scope global 2>/dev/null | grep inet | head -1
fi
