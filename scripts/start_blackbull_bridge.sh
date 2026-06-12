#!/usr/bin/env bash
# Start BlackBull MT5 bridge → pushes XRPUSD + all symbols to Open Trader on :8010
#
# Run on the machine where BlackBull MT5 is open (Windows, or Linux+Wine).
#
# Usage:
#   bash scripts/start_blackbull_bridge.sh
#   bash scripts/start_blackbull_bridge.sh /home/heinz/opentrade-app
#
set -euo pipefail

ENGINE_DIR="${1:-/home/heinz/opentrade-app}"
ENGINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
URL="${OPENTRADER_URL:-http://127.0.0.1:8010}"
PID_FILE="$ENGINE_DIR/.mt5_bridge.pid"
LOG_FILE="$ENGINE_DIR/.mt5_bridge.log"

cd "$ENGINE_DIR"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# .env loaded by mt5_python_bridge.py (dotenv) — do not source here (MT5_PATH spaces)

if ! python -c "import MetaTrader5" 2>/dev/null; then
  echo "MetaTrader5 not available in this Python."
  echo ""
  echo "On LINUX (chart on this PC, MT5 on Windows):"
  echo "  On Windows with BlackBull MT5 open:"
  echo "    set OPENTRADER_URL=http://$(hostname -I 2>/dev/null | awk '{print $1}'):8010"
  echo "    python scripts\\mt5_python_bridge.py --all-symbols --interval 60"
  echo ""
  echo "On WINDOWS (same PC as MT5):"
  echo "  pip install -r requirements-mt5.txt"
  echo "  set OPENTRADER_URL=$URL"
  echo "  python scripts\\mt5_python_bridge.py --all-symbols --interval 60"
  echo ""
  echo "Or start Django backend: bash scripts/start_opentrader_django.sh"
  exit 1
fi

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "MT5 bridge already running (PID $(cat "$PID_FILE"))"
  exit 0
fi

echo "==> Starting MT5 bridge → $URL"
echo "    Log: $LOG_FILE"
echo "    Ensure BlackBull MT5 is open and logged in."

nohup python "$ENGINE_ROOT/scripts/mt5_python_bridge.py" \
  --url "$URL" \
  --all-symbols \
  --timeframes "M1,M5,H1" \
  --interval 60 \
  >>"$LOG_FILE" 2>&1 &

echo $! >"$PID_FILE"
sleep 3
echo "==> Bridge PID $(cat "$PID_FILE")"
echo "    tail -f $LOG_FILE"
echo "    Test: curl -s '$URL/api/candles?symbol=XRPUSD&timeframe=M1&source=blackbull' | head -c 200"
