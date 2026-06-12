#!/usr/bin/env bash
# Open Trader — unified app (chart + Bookmap + strategy + journal + backtest + optimizer)
# Run from repo root:  bash install_and_run.sh
# Force restart on 8010:  FORCE=1 bash install_and_run.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "==> Open Trader unified app setup in: $ROOT"

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

if [[ "$(uname -s)" == "Linux" ]]; then
  echo "==> Linux detected — MetaTrader5 is Windows-only (skipped)."
  echo "    For BlackBull data: export CSV from MT5 → trading_data/blackbull_import/"
  echo "    See opentrader/BLACKBULL_MT5.md"
else
  if [[ -f requirements-mt5.txt ]]; then
    pip install -q -r requirements-mt5.txt || echo "==> MetaTrader5 install skipped (optional, Windows + MT5 only)"
  fi
fi

if [[ ! -f trading_data/eurusd_m1.csv ]]; then
  echo "==> Generating sample data ..."
  python -m trading.fetch_data --output trading_data/eurusd_m1.csv --bars 8000
fi

mkdir -p trading_data/blackbull_import

PORT="${PORT:-8010}"
HOST="${HOST:-127.0.0.1}"

_port_in_use() {
  command -v ss >/dev/null && ss -ltn "sport = :${PORT}" 2>/dev/null | grep -q LISTEN
}

if _port_in_use; then
  if [[ "${FORCE:-0}" == "1" ]]; then
    echo "==> Port ${PORT} in use — stopping existing process (FORCE=1) ..."
    if command -v fuser >/dev/null; then
      fuser -k "${PORT}/tcp" 2>/dev/null || true
    elif command -v lsof >/dev/null; then
      lsof -ti ":${PORT}" | xargs -r kill -9 2>/dev/null || true
    fi
    sleep 1
  else
    echo ""
    echo "Port ${PORT} is already in use."
    echo "  FORCE=1 bash install_and_run.sh   # stop old app and start unified Open Trader"
    echo "  PORT=8011 bash install_and_run.sh # use alternate port"
    exit 1
  fi
fi

echo ""
echo "==> Starting unified Open Trader at http://${HOST}:${PORT}"
echo "    Chart · Bookmap · Strategy · Journal · Backtest · Optimizer — all in one"
echo "    Press Ctrl+C to stop."
exec python -m uvicorn opentrader.main:app --host "$HOST" --port "$PORT"
