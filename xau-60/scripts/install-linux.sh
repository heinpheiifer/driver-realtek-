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
echo "  - UI, backtests, and strategy review run here (mock MT5 data)."
echo "  - For LIVE paper/live trading, run this same app on Windows"
echo "    next to an open MT5 terminal, or use Wine + MT5 (advanced)."
echo ""
echo "Start dashboard on port 8010:"
echo "  ./scripts/start.sh"
echo ""
