#!/usr/bin/env bash
# Open Trader — NEW unified app (chart + Bookmap + strategy + journal + backtest + optimizer)
# Run from repo root:  bash install_and_run.sh
# Force restart on 8010:  FORCE=1 bash install_and_run.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "==> Open Trader setup in: $ROOT"

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
  echo "==> Linux — MetaTrader5 is Windows-only (use Yahoo, CSV, or Windows MT5 bridge)."
  echo "    See opentrader/BLACKBULL_MT5.md"
else
  if [[ -f requirements-mt5.txt ]]; then
    pip install -q -r requirements-mt5.txt || echo "==> MetaTrader5 install skipped (optional)"
  fi
fi

if [[ ! -f trading_data/eurusd_m1.csv ]]; then
  echo "==> Generating sample data ..."
  python -m trading.fetch_data --output trading_data/eurusd_m1.csv --bars 8000
fi

mkdir -p trading_data/blackbull_import

PORT="${PORT:-8010}"
HOST="${HOST:-127.0.0.1}"

# Default: NEW unified app. Legacy chart only with OPENTRADER_USE_OLD_UI=1 in .env
if [[ "${OPENTRADER_USE_OLD_UI:-0}" == "1" ]]; then
  if [[ -z "${OPENTRADER_OLD_APP:-}" ]] && [[ -d "/home/heinz/opentrade-app" ]]; then
    export OPENTRADER_OLD_APP="/home/heinz/opentrade-app"
  fi
  echo "==> Legacy chart UI mode (OPENTRADER_USE_OLD_UI=1)"
  [[ -n "${OPENTRADER_OLD_APP:-}" ]] && echo "    Path: $OPENTRADER_OLD_APP"
else
  unset OPENTRADER_OLD_APP
  echo "==> New Open Trader app (unified UI)"
fi

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
    echo "  FORCE=1 bash install_and_run.sh   # stop and start new Open Trader"
    echo "  PORT=8011 bash install_and_run.sh # alternate port"
    exit 1
  fi
fi

echo ""
echo "==> Starting Open Trader at http://${HOST}:${PORT}"
echo "    Chart · Bookmap · Strategy · Journal · Backtest · Optimizer"
if [[ "$(uname -s)" == "Linux" ]]; then
  echo "    Tip: click Yahoo for live chart data, or run MT5 bridge from Windows"
fi
echo "    Press Ctrl+C to stop."
echo ""
exec python -m uvicorn opentrader.main:app --host "$HOST" --port "$PORT"
