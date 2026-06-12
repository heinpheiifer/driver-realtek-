#!/usr/bin/env bash
# OpenTrade one-shot setup + run. Run from repo root:
#   bash install_and_run.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "==> OpenTrader setup in: $ROOT"

if ! command -v python3 >/dev/null; then
  echo "python3 not found. Install: sudo apt install python3 python3-pip python3-venv"
  exit 1
fi

if ! python3 -c "import venv" 2>/dev/null; then
  echo "python3-venv missing. Run: sudo apt install python3-venv python3-pip"
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "==> Creating .venv ..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing Python packages ..."
pip install -q -r requirements.txt

if [[ ! -f trading_data/eurusd_m1.csv ]]; then
  echo "==> Generating sample data ..."
  python -m trading.fetch_data --output trading_data/eurusd_m1.csv --bars 8000
fi

PORT="${PORT:-8010}"
HOST="${HOST:-127.0.0.1}"

if command -v ss >/dev/null && ss -ltn "sport = :${PORT}" 2>/dev/null | grep -q LISTEN; then
  echo ""
  echo "ERROR: Port ${PORT} is already in use (another OpenTrader instance is running)."
  echo ""
  echo "Stop the old instance, then run this script again:"
  echo "  pkill -f 'uvicorn opentrader.main'"
  echo "  pkill -f 'uvicorn opentrade.main'"
  echo "  bash install_and_run.sh"
  echo ""
  echo "Or find what's using the port:"
  echo "  ss -ltnp | grep :${PORT}"
  echo "  kill <PID>"
  echo ""
  echo "Or use a different port:"
  echo "  PORT=8080 bash install_and_run.sh"
  exit 1
fi

echo "==> Starting OpenTrader at http://${HOST}:${PORT}"
echo "    (includes OpenTrade backtest + optimizer engine)"
echo "    Press Ctrl+C to stop."
exec python -m uvicorn opentrader.main:app --host "$HOST" --port "$PORT"
