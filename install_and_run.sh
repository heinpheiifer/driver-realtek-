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

# If chart UI already on 8010, run research engine on 8011
if [[ "$PORT" == "8010" ]] && command -v ss >/dev/null && ss -ltn "sport = :8010" 2>/dev/null | grep -q LISTEN; then
  echo "==> Port 8010 in use (your Open Trader chart app). Starting engine on 8011."
  PORT=8011
fi

if command -v ss >/dev/null && ss -ltn "sport = :${PORT}" 2>/dev/null | grep -q LISTEN; then
  echo ""
  echo "ERROR: Port ${PORT} is already in use."
  echo "  PORT=8012 bash install_and_run.sh"
  exit 1
fi

echo "==> Starting OpenTrade engine at http://${HOST}:${PORT}"
echo "    Your chart UI can stay on :8010 — point it at this API."
echo "    See opentrader/INTEGRATION.md"
echo "    Press Ctrl+C to stop."
exec python -m uvicorn opentrader.main:app --host "$HOST" --port "$PORT"
