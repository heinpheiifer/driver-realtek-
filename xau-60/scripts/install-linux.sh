#!/usr/bin/env bash
# XAU-60 / MT5 Trading Bot — Linux Mint / Ubuntu install
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> XAU-60 MT5 Trading Bot — install (Linux)"
echo "    Project: $ROOT"
echo ""

if ! command -v python3 >/dev/null; then
  echo "ERROR: python3 not found. Install with: sudo apt install python3 python3-venv python3-pip"
  exit 1
fi

PY_MINOR="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if ! python3 -m venv --help >/dev/null 2>&1; then
  echo "==> Installing python${PY_MINOR}-venv..."
  sudo apt-get update -qq
  sudo apt-get install -y "python${PY_MINOR}-venv" python3-pip
fi

if [[ ! -d .venv ]]; then
  echo "==> Creating virtual environment..."
  python3 -m venv .venv
fi

echo "==> Installing Python packages..."
.venv/bin/pip install -U pip wheel
.venv/bin/pip install -r requirements.txt

mkdir -p logs data

if [[ ! -f .env ]]; then
  echo "==> Creating .env from template..."
  cp .env.example .env
  echo ""
  echo "IMPORTANT: Edit .env with your MT5 demo credentials:"
  echo "  MT5_LOGIN=your_account_number"
  echo "  MT5_PASSWORD=your_password"
  echo "  MT5_SERVER=YourBroker-Demo"
  echo ""
fi

chmod +x scripts/start.sh scripts/install-linux.sh 2>/dev/null || true

echo ""
echo "==> Install complete."
echo ""
echo "NOTE (Linux Mint): MetaTrader5 live API only works on Windows."
echo "  - If MT5 runs in Wine on THIS laptop:"
echo "      1) wine python -m pip install MetaTrader5 mt5linux"
echo "      2) pip install mt5linux  (Linux venv — done by install script)"
echo "      3) Set MT5_WINE_ENABLED=true in .env"
echo "      4) ./scripts/start-wine-mt5linux.sh  (with MT5 open in Wine)"
echo "  - Or use a remote Windows PC with MT5_BRIDGE_URL (see SETUP_XAU60.md)."
echo ""
echo "Start dashboard on port 8020 (8010 = Tradenator):"
echo "  ./scripts/start.sh"
echo ""
