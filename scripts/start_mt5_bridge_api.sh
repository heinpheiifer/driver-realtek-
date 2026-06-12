#!/usr/bin/env bash
# Start MT5 BlackBull bridge API for the Open Trader OLD chart app.
# If your chart UI is already on :8010, this runs the data API on :8011.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PORT="${PORT:-8011}"
if ss -ltn "sport = :8010" 2>/dev/null | grep -q LISTEN; then
  echo "==> Old Open Trader chart detected on :8010"
  echo "    Starting MT5 bridge API on :8011"
  PORT=8011
fi

source .venv/bin/activate 2>/dev/null || bash install_and_run.sh &
sleep 2

echo ""
echo "MT5 bridge API: http://127.0.0.1:${PORT}"
echo "Old chart app:   http://127.0.0.1:8010  (point BlackBull feed to :${PORT})"
echo ""
echo "Endpoints for old app:"
echo "  GET  /api/symbols              — all BlackBull symbols"
echo "  GET  /api/candles?symbol=XRPUSD&timeframe=M1&source=blackbull"
echo "  GET  /api/bookmap/stream       — order flow"
echo ""
echo "On Windows (BlackBull MT5), run:"
echo "  set OPENTRADER_URL=http://127.0.0.1:${PORT}"
echo "  python scripts/mt5_python_bridge.py --all-symbols --interval 60"
echo ""

exec python -m uvicorn opentrader.main:app --host 127.0.0.1 --port "$PORT"
