#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

install_deps() {
  if python3 -m pip install -r requirements.txt; then
    return 0
  fi
  echo "Trying pip install --user ..."
  python3 -m pip install --user -r requirements.txt
}

if [[ ! -d .venv ]]; then
  if python3 -m venv .venv 2>/dev/null; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
    pip install -q -r requirements.txt
  else
    echo "Note: python3-venv not available. Install with: sudo apt install python3-venv python3-pip"
    echo "Installing packages for current user instead ..."
    install_deps
  fi
else
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -q -r requirements.txt
fi

python3 -m trading.fetch_data --output trading_data/eurusd_m1.csv --bars 8000 2>/dev/null || true
echo "Setup complete. Run: bash scripts/run_opentrade.sh"
