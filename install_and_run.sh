#!/usr/bin/env bash
# Open Trader — serves YOUR old chart app when /home/heinz/opentrade-app exists
# Run from repo root:  bash install_and_run.sh
# Force restart:       FORCE=1 bash install_and_run.sh
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
  echo "==> Linux — MetaTrader5 package is Windows-only."
else
  if [[ -f requirements-mt5.txt ]]; then
    pip install -q -r requirements-mt5.txt || true
  fi
fi

if [[ ! -f trading_data/eurusd_m1.csv ]]; then
  echo "==> Generating sample data ..."
  python -m trading.fetch_data --output trading_data/eurusd_m1.csv --bars 8000
fi

mkdir -p trading_data/blackbull_import

PORT="${PORT:-8010}"
HOST="${HOST:-127.0.0.1}"

# Default: YOUR old chart at /home/heinz/opentrade-app (set OPENTRADER_USE_NEW_UI=1 for git UI)
if [[ "${OPENTRADER_USE_NEW_UI:-0}" == "1" ]]; then
  unset OPENTRADER_OLD_APP
  echo "==> New unified app UI (OPENTRADER_USE_NEW_UI=1)"
else
  export OPENTRADER_USE_OLD_UI=1
  if [[ -z "${OPENTRADER_OLD_APP:-}" ]] && [[ -d "/home/heinz/opentrade-app" ]]; then
    export OPENTRADER_OLD_APP="/home/heinz/opentrade-app"
  fi
  if [[ -n "${OPENTRADER_OLD_APP:-}" ]] && [[ -d "$OPENTRADER_OLD_APP" ]]; then
    echo "==> Your old Open Trader chart UI: $OPENTRADER_OLD_APP"
  else
    echo "==> Old app path not found — serving built-in UI"
    echo "    Run: bash scripts/bring_back_old_app.sh"
  fi
fi

_port_in_use() {
  command -v ss >/dev/null && ss -ltn "sport = :${PORT}" 2>/dev/null | grep -q LISTEN
}

if _port_in_use; then
  if [[ "${FORCE:-0}" == "1" ]]; then
    echo "==> Port ${PORT} in use — stopping (FORCE=1) ..."
    if command -v fuser >/dev/null; then
      fuser -k "${PORT}/tcp" 2>/dev/null || true
    elif command -v lsof >/dev/null; then
      lsof -ti ":${PORT}" | xargs -r kill -9 2>/dev/null || true
    fi
    sleep 1
  else
    echo ""
    echo "Port ${PORT} is already in use."
    echo "  FORCE=1 bash install_and_run.sh"
    exit 1
  fi
fi

echo ""
echo "==> Starting at http://${HOST}:${PORT}"
echo "    Press Ctrl+C to stop."
echo ""
exec python -m uvicorn opentrader.main:app --host "$HOST" --port "$PORT"
